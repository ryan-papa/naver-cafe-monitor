"""1회 실행 배치 스크립트.

cron으로 30분마다 호출되어 새 게시물을 확인하고 처리한다.
- 사진 게시판(menus/13): 새 게시물 감지 → 카카오톡 알림 (전달사항 + 사진 장수)
- 공지사항(menus/6): 이미지 다운로드 → Claude CLI 분석 → 카카오톡 요약 전송

실행: python -m src.batch
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from src.config import load_config
from src.crawler.image_downloader import ImageDownloader
from src.crawler.post_tracker import DbStore, JsonFileStore
from src.crawler.session import build_context, restore_cookies
from src.messaging.kakao import KakaoMessenger
from src.messaging.kakao_auth import KakaoAuth
from src.notice.summarizer import Summarizer

# shared 모듈 import (pymysql 미설치 환경에서는 graceful 폴백)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from shared.database import get_connection  # noqa: E402
    from shared.post_repository import PostRepository  # noqa: E402
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CAFE_URL = "https://cafe.naver.com/f-e/cafes/31672965"
_PHOTO_ALBUM_ID = "AMjg2hP8k5198eTgkM9kcQO_IGEQAoqo-3uGqo8GCnKjGzhIDkfEzfkjsv22_h_oBzyWyQl8NqcA"
_PHOTO_ALBUM_URL = "https://photos.google.com/album/AF1QipO6xY0TO1r6l9Qdp_bytBU-w0A5ZiRxLs_4KvYM"
_NOTICE_MAX_RETRIES = 3
_NOTICE_RETRY_DELAY_SECONDS = 5.0
_NOTICE_DB_SAVE_MAX_RETRIES = 3


class NoticeProcessingError(RuntimeError):
    """공지 처리 단계가 포함된 예외."""

    def __init__(self, stage: str, exc: Exception) -> None:
        self.stage = stage
        self.original = exc
        super().__init__(f"{stage}: {exc}")


def _notice_stage_error(stage: str, exc: Exception) -> NoticeProcessingError:
    if isinstance(exc, NoticeProcessingError):
        return exc
    return NoticeProcessingError(stage, exc)


def _check_refresh_token_alert(auth: KakaoAuth, kakao: KakaoMessenger) -> None:
    """refresh token 만료 임박 시 WARNING 로그 + 카카오톡 알림 (하루 1회)."""
    days_left = auth.check_refresh_token_expiry()
    if days_left is None:
        return

    if not auth.should_alert_today():
        return

    msg = f"[카카오 토큰 알림] refresh token 만료까지 {days_left}일 남았습니다. 재인증이 필요합니다."
    logger.warning(msg)

    try:
        kakao.send_text(msg)
        auth.mark_alert_sent()
        logger.info("refresh token 만료 알림 전송 완료")
    except Exception as e:
        logger.error("refresh token 만료 알림 전송 실패: %s", e)


def _filter_image_urls(urls: list[str]) -> list[str]:
    """phinf.pstatic.net + JPEG 이미지만 필터링, ?이전까지."""
    filtered = []
    for url in urls:
        if "phinf.pstatic.net" not in url:
            continue
        if "JPEG" not in url.upper():
            continue
        clean = url.split("?")[0]
        filtered.append(clean)
    return filtered


async def _fetch_new_articles(
    context, menu_id: str, last_seen_id: int,
) -> list[dict]:
    """게시판에서 last_seen 이후의 새 게시물을 수집한다."""
    page = await context.new_page()
    try:
        board_url = f"{_CAFE_URL}/menus/{menu_id}"
        await page.goto(board_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # cafe_main iframe 접근
        frame = page.frame("cafe_main") or page.main_frame
        links = await frame.query_selector_all("a[class*=article]")

        articles = []
        for link in links:
            href = await link.get_attribute("href") or ""
            m = re.search(r"/(\d+)(?:\?|$)", href)
            if not m:
                continue
            post_id = int(m.group(1))
            if post_id <= last_seen_id:
                continue
            title = (await link.inner_text()).strip()
            full_url = f"https://cafe.naver.com{href}" if href.startswith("/") else href
            articles.append({"post_id": post_id, "title": title, "url": full_url})

        articles.sort(key=lambda a: a["post_id"])
        return articles
    finally:
        await page.close()


async def _fetch_post_detail(context, post_url: str) -> dict:
    """게시물 상세에서 이미지 URL + 텍스트 본문을 수집한다."""
    page = await context.new_page()
    try:
        await page.goto(post_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        frame = page.frame("cafe_main") or page.main_frame
        body = await frame.query_selector(".se-main-container, #postContent, .article-viewer")
        if not body:
            return {"images": [], "text": ""}

        # 이미지
        img_els = await body.query_selector_all("img")
        urls = []
        for img in img_els:
            src = await img.get_attribute("src") or await img.get_attribute("data-src") or ""
            if src.strip() and not src.startswith("data:"):
                urls.append(src.strip())

        # 텍스트 본문
        text = await body.inner_text()

        return {"images": urls, "text": text.strip()}
    finally:
        await page.close()


async def _process_photo_board(
    context, last_seen: dict, kakao: KakaoMessenger,
    summarizer: Summarizer,
    repo: PostRepository | None = None,
) -> None:
    """사진 게시판(menus/13) 처리: 새 게시물 감지 → 카카오톡 알림."""
    menu_key = "menus/13"
    last_id = int(last_seen.get(menu_key, 0))
    articles = await _fetch_new_articles(context, "13", last_id)

    if not articles:
        logger.info("[사진] 새 게시물 없음")
        return

    if last_id == 0:
        logger.info("[사진] 최초 실행 — 최신 1건만 처리")
        articles = [articles[-1]]

    max_id = last_id

    for article in articles:
        pid = article["post_id"]
        title = article["title"]
        post_link = article["url"]
        logger.info("[사진] 새 게시물: #%d %s", pid, title)

        detail = await _fetch_post_detail(context, post_link)
        image_urls = _filter_image_urls(detail["images"])
        body_text = detail["text"]
        photo_count = len(image_urls)

        # 카카오톡 알림 (전달사항 + 사진 정보 통합 1건)
        if body_text:
            notice = summarizer.summarize_short(body_text)
            msg = f"[세화유치원 사진]\n\n📝 {title}\n\n{notice}"
            if photo_count:
                msg += f"\n\n📷 사진 {photo_count}장"
        elif photo_count:
            msg = f"[세화유치원 사진]\n\n📷 {title}\n사진 {photo_count}장"
        else:
            msg = f"[세화유치원 사진]\n\n📷 {title}"

        kakao.send_text(msg, link_url=post_link, button_label="카페에서 보기")
        logger.info("[사진] 알림 전송 완료: #%d", pid)

        # DB 기록
        if repo:
            try:
                summary_text = summarizer.summarize_short(body_text) if body_text else None
                repo.save(
                    board_id=menu_key, post_id=pid, title=title,
                    summary=summary_text, image_count=photo_count, status="SUCCESS",
                )
            except Exception as e:
                logger.error("[사진] DB 기록 실패: %s", e)

        max_id = max(max_id, pid)

    last_seen[menu_key] = max_id


def _save_notice_result(
    repo: PostRepository | None,
    *,
    menu_key: str,
    post_id: int,
    title: str,
    summary: str | None,
    image_count: int,
    status: str,
) -> None:
    """공지 처리 결과를 DB에 저장한다."""
    if repo is None:
        return
    repo.save(
        board_id=menu_key,
        post_id=post_id,
        title=title,
        summary=summary,
        image_count=image_count,
        status=status,
    )


async def _save_notice_result_with_retry(
    repo: PostRepository | None,
    *,
    menu_key: str,
    post_id: int,
    title: str,
    summary: str | None,
    image_count: int,
    status: str,
    max_retries: int = _NOTICE_DB_SAVE_MAX_RETRIES,
    retry_delay_seconds: float = _NOTICE_RETRY_DELAY_SECONDS,
) -> bool:
    """공지 처리 결과 DB 저장만 재시도한다."""
    max_attempts = max_retries + 1
    for attempt in range(1, max_attempts + 1):
        try:
            _save_notice_result(
                repo,
                menu_key=menu_key,
                post_id=post_id,
                title=title,
                summary=summary,
                image_count=image_count,
                status=status,
            )
            return True
        except Exception as exc:
            if attempt < max_attempts:
                logger.warning(
                    "[공지] %s DB 기록 실패, 재시도 %d/%d: #%d %s — %s",
                    status,
                    attempt,
                    max_retries,
                    post_id,
                    title,
                    exc,
                )
                await asyncio.sleep(retry_delay_seconds)
            else:
                logger.error(
                    "[공지] %s DB 기록 최종 실패 (총 %d회 시도): #%d %s — %s",
                    status,
                    max_attempts,
                    post_id,
                    title,
                    exc,
                )
    return False


async def _process_notice_article_once(
    context,
    *,
    menu_key: str,
    article: dict,
    kakao: KakaoMessenger,
    summarizer: Summarizer,
    downloader: ImageDownloader,
    repo: PostRepository | None = None,
) -> bool:
    """공지 게시글 1건을 한 번 처리하고 이력 저장 성공 여부를 반환한다."""
    pid = article["post_id"]
    title = article["title"]
    post_url = article["url"]

    try:
        detail = await _fetch_post_detail(context, post_url)
    except Exception as exc:
        raise _notice_stage_error("detail_fetch", exc) from exc

    image_urls = _filter_image_urls(detail["images"])
    summaries = []

    if image_urls:
        try:
            paths = await downloader.download_all(str(pid), image_urls)
        except Exception as exc:
            raise _notice_stage_error("image_download", exc) from exc
        if not paths:
            raise NoticeProcessingError(
                "image_download",
                RuntimeError(f"다운로드 성공 이미지 0/{len(image_urls)}장"),
            )

        # Claude 분석
        for path in paths:
            try:
                result = summarizer.analyze_image(path)
                summaries.append(result)
            except Exception as e:
                logger.warning("[공지] 이미지 분석 실패: %s — %s", path.name, e)
                raise _notice_stage_error("image_analysis", e) from e

        if summaries:
            combined = "\n\n---\n\n".join(summaries)
            try:
                kakao.send_notice_summary(title, combined, post_url=post_url)
            except Exception as exc:
                raise _notice_stage_error("kakao_send", exc) from exc
            logger.info("[공지] 요약 전송 완료: %s", title)
    else:
        logger.info("[공지] 이미지 없는 공지, 제목만 전송")
        try:
            kakao.send_text(f"[세화유치원 공지]\n\n📋 {title}")
        except Exception as exc:
            raise _notice_stage_error("kakao_send", exc) from exc

    db_summary = "\n\n---\n\n".join(summaries) if summaries else None
    saved = await _save_notice_result_with_retry(
        repo,
        menu_key=menu_key,
        post_id=pid,
        title=title,
        summary=db_summary,
        image_count=len(image_urls),
        status="SUCCESS",
    )
    if not saved:
        return False
    return True


async def _process_notice_article_with_retry(
    context,
    *,
    menu_key: str,
    article: dict,
    kakao: KakaoMessenger,
    summarizer: Summarizer,
    downloader: ImageDownloader,
    repo: PostRepository | None = None,
    max_retries: int = _NOTICE_MAX_RETRIES,
    retry_delay_seconds: float = _NOTICE_RETRY_DELAY_SECONDS,
) -> bool:
    """공지 게시글 1건을 재시도 포함 처리하고 성공 여부를 반환한다."""
    pid = article["post_id"]
    title = article["title"]
    last_exc: Exception | None = None
    max_attempts = max_retries + 1

    for attempt in range(1, max_attempts + 1):
        try:
            processed = await _process_notice_article_once(
                context,
                menu_key=menu_key,
                article=article,
                kakao=kakao,
                summarizer=summarizer,
                downloader=downloader,
                repo=repo,
            )
            return processed
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                logger.warning(
                    "[공지] 처리 실패, 재시도 %d/%d: #%d %s — %s",
                    attempt,
                    max_retries,
                    pid,
                    title,
                    exc,
                )
                await asyncio.sleep(retry_delay_seconds)
            else:
                logger.error(
                    "[공지] 최종 실패 (총 %d회 시도): #%d %s — %s",
                    max_attempts,
                    pid,
                    title,
                    exc,
                )

    if isinstance(last_exc, NoticeProcessingError):
        failure_summary = (
            f"처리 실패 단계: {last_exc.stage}\n"
            f"오류: {last_exc.original}"
        )
    else:
        failure_summary = f"처리 실패: {last_exc}" if last_exc else "처리 실패"
    return await _save_notice_result_with_retry(
        repo,
        menu_key=menu_key,
        post_id=pid,
        title=title,
        summary=failure_summary,
        image_count=0,
        status="FAIL",
    )


async def _process_notice_board(
    context, last_seen: dict, kakao: KakaoMessenger,
    summarizer: Summarizer,
    repo: PostRepository | None = None,
) -> None:
    """공지사항(menus/6) 처리: 이미지 → Claude 분석 → 카카오톡."""
    menu_key = "menus/6"
    last_id = int(last_seen.get(menu_key, 0))
    articles = await _fetch_new_articles(context, "6", last_id)

    if not articles:
        logger.info("[공지] 새 게시물 없음")
        return

    if last_id == 0:
        logger.info("[공지] 최초 실행 — 최신 1건만 처리")
        articles = [articles[-1]]

    downloader = ImageDownloader()
    max_id = last_id

    for article in articles:
        pid = article["post_id"]
        title = article["title"]
        logger.info("[공지] 새 게시물: #%d %s", pid, title)

        processed = await _process_notice_article_with_retry(
            context,
            menu_key=menu_key,
            article=article,
            kakao=kakao,
            summarizer=summarizer,
            downloader=downloader,
            repo=repo,
        )
        if processed:
            max_id = max(max_id, pid)
        else:
            logger.error("[공지] 이력 저장 실패로 이후 공지 처리를 중단합니다: #%d %s", pid, title)
            break

    last_seen[menu_key] = max_id


def _load_last_seen(db_conn=None) -> dict:
    """last_seen을 로딩한다. DB 연결 시 DB 우선, 아니면 파일."""
    if db_conn:
        store = DbStore(db_conn)
    else:
        store = JsonFileStore()
    data = store.load()
    return {k: int(v) for k, v in data.items()}


def _save_last_seen(data: dict, db_conn=None) -> None:
    """last_seen을 저장한다. DB 모드면 no-op (개별 INSERT로 기록)."""
    if db_conn:
        store = DbStore(db_conn)
    else:
        store = JsonFileStore()
    store.save({k: str(v) for k, v in data.items()})


async def run() -> None:
    """배치 메인 로직."""
    config = load_config()

    # 카카오 인증 + 메신저 초기화
    kakao_auth = KakaoAuth(
        client_id=config.kakao_client_id,
        client_secret=config.kakao_client_secret,
    )
    kakao = KakaoMessenger(auth=kakao_auth)
    summarizer = Summarizer.from_config(config)

    # refresh token 만료 알림 체크
    _check_refresh_token_alert(kakao_auth, kakao)

    # DB 연결
    repo = None
    db_conn = None
    if _DB_AVAILABLE:
        try:
            db_conn = get_connection()
            repo = PostRepository(db_conn)
            logger.info("DB 연결 성공")
        except Exception as e:
            logger.warning("DB 연결 실패 — 파일 모드로 폴백: %s", e)

    # last_seen 로딩 (DB 우선, 파일 폴백)
    last_seen = _load_last_seen(db_conn)

    async with async_playwright() as pw:
        context = await build_context(pw, headless=True)
        restored = await restore_cookies(context)
        if not restored:
            logger.error("쿠키 없음. 먼저 수동 로그인 필요: python -m src.crawler.login")
            await context.close()
            sys.exit(1)

        try:
            await _process_photo_board(context, last_seen, kakao, summarizer, repo)
            await _process_notice_board(context, last_seen, kakao, summarizer, repo)
        finally:
            _save_last_seen(last_seen, db_conn)
            if db_conn:
                db_conn.close()
            await context.close()

    logger.info("배치 완료")


def main() -> None:
    """엔트리포인트."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
