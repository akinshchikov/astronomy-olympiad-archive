from __future__ import annotations

import html
import re
from urllib.parse import urljoin

from .fs_utils import normalize_whitespace

ANCHOR_RE = re.compile(
    r"<a\b[^>]*href=(?P<quote>['\"])(?P<href>.*?)(?P=quote)[^>]*>(?P<text>.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", flags=re.IGNORECASE | re.DOTALL)


def strip_tags(raw_html: str) -> str:
    text = TAG_RE.sub(" ", raw_html)
    text = html.unescape(text)
    return normalize_whitespace(text)


def extract_title(raw_html: str) -> str:
    match = TITLE_RE.search(raw_html)
    if not match:
        return ""
    return strip_tags(match.group(1))


def extract_links(raw_html: str, base_url: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in ANCHOR_RE.finditer(raw_html):
        href = html.unescape(match.group("href")).strip()
        if not href:
            continue
        absolute = urljoin(base_url, href)
        text = strip_tags(match.group("text"))
        key = (absolute, text)
        if key in seen:
            continue
        seen.add(key)
        links.append({"href": absolute, "text": text})
    return links


def html_to_text(raw_html: str) -> str:
    text = strip_tags(raw_html)
    return text + "\n" if text else ""

