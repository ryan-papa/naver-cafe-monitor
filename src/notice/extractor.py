"""공지사항 텍스트 추출 및 정제 모듈 (T-08).

PostDetail의 body_text에서 HTML 태그를 제거하고,
불필요한 공백·줄바꿈을 정리한 뒤 날짜·일정 패턴을 감지한다.
"""
from __future__ import annotations

import re

from src.crawler.parser import PostDetail

# ── 날짜 패턴 정규식 ──────────────────────────────────────────────────────────

# YYYY년 MM월 DD일, YYYY년 M월 D일
_PATTERN_KOR = re.compile(r"\d{4}년\s*\d{1,2}월\s*\d{1,2}일")

# YYYY-MM-DD, YYYY.MM.DD
_PATTERN_ISO = re.compile(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}")

# MM/DD, MM.DD
_PATTERN_MMDD = re.compile(r"\d{1,2}[/\.]\d{1,2}")

# HH:MM ~ HH:MM, HH시 MM분
_PATTERN_TIME = re.compile(r"\d{1,2}:\d{2}(?:\s*~\s*\d{1,2}:\d{2})?|\d{1,2}시(?:\s*\d{1,2}분)?")

# 기간 표현: N일간, N박 N일
_PATTERN_PERIOD = re.compile(r"\d+일간|\d+박\s*\d+일")

_ALL_DATE_PATTERNS = [
    _PATTERN_KOR,
    _PATTERN_ISO,
    _PATTERN_MMDD,
    _PATTERN_TIME,
    _PATTERN_PERIOD,
]

# ── HTML 제거 ─────────────────────────────────────────────────────────────────

_TAG_RE = re.compile(r"<[^>]+>")
_ENTITY_MAP = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&nbsp;": " ",
}
_ENTITY_RE = re.compile(r"&[a-zA-Z0-9#]+;")


def _remove_html(text: str) -> str:
    """HTML 태그 및 엔티티를 제거한다."""
    text = _TAG_RE.sub(" ", text)
    def _replace_entity(m: re.Match) -> str:
        return _ENTITY_MAP.get(m.group(), "")
    return _ENTITY_RE.sub(_replace_entity, text)


def _normalize_whitespace(text: str) -> str:
    """연속 공백과 과도한 빈 줄을 정리한다."""
    # 탭·폼피드 등을 스페이스로
    text = re.sub(r"[^\S\n]+", " ", text)
    # 3줄 이상 연속 빈 줄 → 2줄로
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 줄 앞뒤 여백 제거
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)
    return text.strip()


# ── 날짜 패턴 감지 ────────────────────────────────────────────────────────────

def detect_date_patterns(text: str) -> list[str]:
    """텍스트에서 날짜·일정 패턴 문자열 목록을 반환한다."""
    found: list[str] = []
    for pattern in _ALL_DATE_PATTERNS:
        for m in pattern.finditer(text):
            found.append(m.group())
    return found


# ── 공개 API ──────────────────────────────────────────────────────────────────

def extract(post_detail: PostDetail) -> str:
    """PostDetail의 본문을 정제하여 순수 텍스트를 반환한다.

    처리 순서:
    1. HTML 태그 및 엔티티 제거
    2. 공백·줄바꿈 정규화
    """
    raw = post_detail.body_text
    cleaned = _remove_html(raw)
    cleaned = _normalize_whitespace(cleaned)
    return cleaned
