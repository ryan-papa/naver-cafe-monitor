"""공지사항 AI 요약 모듈.

Claude Code CLI를 사용하여 공지 텍스트 및 이미지를 분석한다.
별도 API 키 불필요 — 로컬 Claude Code 인증을 그대로 사용.
이미지는 분할 후 각각 분석하여 정확도를 높인다.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from src.config import Config

logger = logging.getLogger(__name__)

_TEXT_PROMPT = """\
다음 유치원 공지사항을 읽고 아래 형식으로 정리해줘.
마크다운(**, ##, | 등) 사용 금지. 카카오톡 메시지용이라 순수 텍스트만 사용.

[전체 내용 요약]
• 항목1
• 항목2

[일정 정리]
- 날짜 / 내용 / 대상
- 날짜 / 내용 / 대상

---
{text}
"""

_IMAGE_PROMPT = """\
먼저 Read 도구로 {image_path} 파일을 읽어.
유치원 공지사항 이미지야. 이미지 내 모든 텍스트를 정확히 읽고 분석해줘.
마크다운(**, ##, | 등) 사용 금지. 카카오톡 메시지용이라 순수 텍스트만 사용.
중요: 5세/6세/7세 등 연령별 활동·일정·대상을 반드시 구분하여 표기. 나이 정보 생략 금지.

[내용 정리]
• 항목1 (대상: X세)
• 항목2 (대상: 전체)

[일정 정리]
- 날짜 / 내용 / 대상(X세)
"""

_MERGE_PROMPT = """\
아래는 유치원 공지사항 이미지를 분할 분석한 결과야.
이것을 하나의 공지 요약으로 통합 정리해줘.
중복 제거, 일정은 날짜순 정렬.
마크다운(**, ##, | 등) 사용 금지. 카카오톡 메시지용이라 순수 텍스트만 사용.
중요: 5세/6세/7세 등 연령별 활동·일정을 반드시 구분하여 표기. 나이 정보 생략 금지.

• 항목별 불릿 (대상: X세)

[일정 정리]
- 날짜 / 내용 / 대상(X세)

---
{parts}
"""


class Summarizer:
    """공지사항을 Claude Code CLI로 요약하는 클래스."""

    def __init__(self, model: str = "opus", claude_path: str = "claude") -> None:
        self._model = model
        self._claude_path = claude_path

    @classmethod
    def from_config(cls, config: "Config") -> "Summarizer":
        model = getattr(config.summary, "model", "opus")
        return cls(model=model)

    def _run_cli(self, prompt: str, timeout: int = 120, tools: str | None = None) -> str:
        cmd = [self._claude_path, "-p", prompt, "--model", self._model]
        if tools:
            cmd.extend(["--allowedTools", tools])
        logger.debug("Claude CLI 호출: model=%s, cmd=%s", self._model, " ".join(cmd[:4]))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(Path.cwd()))
            if result.returncode != 0:
                logger.error("Claude CLI 실패: returncode=%d, stderr=%s, stdout=%s", result.returncode, result.stderr[:200], result.stdout[:200])
                raise RuntimeError(f"Claude CLI 실패: rc={result.returncode} stderr={result.stderr[:200]} stdout={result.stdout[:200]}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Claude CLI 타임아웃 ({timeout}초)")

    def summarize(self, text: str) -> str:
        """공지 텍스트를 요약한다."""
        if not text.strip():
            return ""
        return self._run_cli(_TEXT_PROMPT.format(text=text), timeout=60)

    def _split_image(self, image_path: Path, parts: int = 2) -> list[Path]:
        """이미지를 세로로 분할한다."""
        img = Image.open(image_path)
        w, h = img.size
        chunk_h = h // parts
        split_paths = []
        for i in range(parts):
            top = i * chunk_h
            bottom = h if i == parts - 1 else (i + 1) * chunk_h
            cropped = img.crop((0, top, w, bottom))
            out = image_path.parent / f"{image_path.stem}_part{i}{image_path.suffix}"
            cropped.save(out)
            split_paths.append(out)
        logger.info("이미지 %d분할 완료: %s", parts, image_path.name)
        return split_paths

    def analyze_image(self, image_path: str | Path) -> str:
        """공지사항 이미지를 분할 분석 후 통합 요약한다."""
        path = Path(image_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"이미지 파일 없음: {path}")

        # 이미지 분할
        split_paths = self._split_image(path, parts=2)

        # 각 파트 분석
        parts_results = []
        for i, sp in enumerate(split_paths):
            logger.info("파트 %d/%d 분석 중...", i + 1, len(split_paths))
            prompt = _IMAGE_PROMPT.format(image_path=str(sp.resolve()))
            result = self._run_cli(prompt, timeout=120, tools="Read")
            parts_results.append(f"[파트 {i + 1}]\n{result}")

        # 통합 요약
        merged_text = "\n\n".join(parts_results)
        logger.info("통합 요약 중...")
        return self._run_cli(
            _MERGE_PROMPT.format(parts=merged_text), timeout=60
        )
