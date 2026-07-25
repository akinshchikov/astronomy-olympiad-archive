from __future__ import annotations

import csv
import hashlib
import re
import sys
from html.parser import HTMLParser
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from utils.cli import build_common_parser
from utils.fs_utils import ensure_dir, normalize_whitespace, write_jsonl
from utils.html_utils import extract_links, extract_title, html_to_text
from utils.http_utils import HttpClient
from utils.logging_utils import configure_logger
from utils.metadata import (
    confidence_score,
    decoded_filename,
    decoded_url_path,
    infer_document_type,
    infer_extension,
    infer_language,
    logical_document_types,
    infer_stage,
    infer_variant_tag,
    infer_year,
    source_domain,
)
from utils.source_configs import SOURCE_DEFINITIONS, iter_seed_requests


ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "zip", "html", "htm"}
DIRECT_FILE_EXTENSIONS = {"pdf", "doc", "docx", "zip"}
STRUVE_SOURCE_ID = "struve_moscow_year_pages"
STRUVE_ASTROEDU_SOURCE_ID = "struve_astroedu_archive"
OWAO_SOURCE_ID = "owao_tasks_official"
OWAO_ASTROEDU_SOURCE_ID = "owao_astroedu_archive"
SERBIA_SOURCE_ID = "serbia_astronomy_official"
RUSSIA_TEAM_QUAL_SOURCE_ID = "russia_team_qual_archive"
VSOSH_ASTROEDU_SOURCE_ID = "vsosh_astroedu_archive"
VSOSH_EDSOO_SOURCE_ID = "vsosh_edsoo_stage_documents"
VSOSH_MOSCOW_TEAM_SOURCE_ID = "vsosh_moscow_team_year"
VSOSH_SIRIUS_SOURCE_ID = "vsosh_sirius_final"
SPBAO_OFFICIAL_SOURCE_ID = "spbao_official"
IOAA_JUNIOR_SOURCE_ID = "ioaa_junior_official"
USAAAO_SOURCE_ID = "usaaao_past_exams"
INAO_SOURCE_IDS = {"inao_hbcse_past_papers", "inao_hbcse_current"}
CZECH_SOURCE_ID = "czech_astronomy_official"
GECAA_SOURCE_IDS = {"gecaa_ioaa_archive", "gecaa_official_archive"}
IOAA_CORE_SOURCE_IDS = {"ioaa_problems", "ioaa_proceedings", "ioaa_past_olympiads"}
SKIP_SEED_PAGE_SOURCE_IDS = {STRUVE_SOURCE_ID, STRUVE_ASTROEDU_SOURCE_ID, "mao_official_archive"}
CURRENT_YEAR = datetime.now().year
SERBIA_ARCHIVE_PATTERNS = (
    (re.compile(r"^OpstCont(?P<year>\d{4})\.pdf$", flags=re.IGNORECASE), "qualifying"),
    (re.compile(r"^RegioCont(?P<year>\d{4})\.pdf$", flags=re.IGNORECASE), "regional"),
    (re.compile(r"^RepubCont(?P<year>\d{4})\.pdf$", flags=re.IGNORECASE), "final"),
)
OWAO_PAGE_TOKEN_RE = re.compile(
    r"<(?P<heading>h[1-6])\b[^>]*>(?P<heading_text>.*?)</(?P=heading)>"
    r"|<div\b[^>]*\bfield=(?P<quote>['\"])(?:tn_text_[^'\"]+|text)(?P=quote)[^>]*>(?P<label_text>.*?)</div>"
    r"|<a\b[^>]*>(?P<anchor_text>.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)


class OrderedPageParser(HTMLParser):
    """Collect links and table rows while retaining nearby textual context."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url, self.tokens, self.rows = base_url, [], []
        self._href: str | None = None
        self._anchor_text: list[str] = []
        self._row_depth, self._row_text, self._row_links = 0, [], []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "tr":
            self._row_depth += 1
            if self._row_depth == 1:
                self._row_text, self._row_links = [], []
        if tag.lower() == "a" and (href := dict(attrs).get("href")):
            self._href, self._anchor_text = urljoin(self.base_url, href.strip()), []

    def handle_data(self, data: str) -> None:
        text = normalize_whitespace(data)
        if not text:
            return
        (self._anchor_text if self._href else self.tokens).append(text if self._href else {"kind": "text", "text": text})
        if self._row_depth:
            self._row_text.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            link = {"href": self._href, "text": normalize_whitespace(" ".join(self._anchor_text))}
            self.tokens.append({"kind": "link", **link})
            if self._row_depth:
                self._row_links.append(link)
            self._href, self._anchor_text = None, []
        if tag.lower() == "tr" and self._row_depth:
            self._row_depth -= 1
            if not self._row_depth:
                self.rows.append({"text": normalize_whitespace(" ".join(self._row_text)), "links": list(self._row_links)})


def parsed_page(raw_html: str, base_url: str) -> OrderedPageParser:
    parser = OrderedPageParser(base_url)
    parser.feed(raw_html)
    parser.close()
    return parser


def build_source_candidates_csv(root: Path, families: set[str] | None) -> list[dict]:
    rows: list[dict] = []
    for source in SOURCE_DEFINITIONS:
        if families and source.olympiad_family not in families:
            continue
        seeds = iter_seed_requests(source)
        rows.append(
            {
                "source_id": source.source_id,
                "label": source.label,
                "olympiad_family": source.olympiad_family,
                "source_role": source.source_role,
                "source_priority": source.source_priority,
                "seed_count": len(seeds),
                "notes": source.notes,
            }
        )

    out_path = root / "data" / "manifests" / "source_candidates.csv"
    ensure_dir(out_path.parent)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    return rows


def should_record_link(url: str) -> bool:
    decoded_path = decoded_url_path(url).lower()
    if any(decoded_path.endswith(f".{extension}") for extension in ALLOWED_EXTENSIONS):
        return True
    return False


def source_id_of(seed: dict) -> str:
    return str(seed.get("source_id", ""))


def is_source_seed(seed: dict, source_id: str) -> bool:
    return source_id_of(seed) == source_id


def seed_context(seed: dict) -> dict:
    return dict(seed.get("context") or {})


def context_year(context: dict) -> int | None:
    for key in ("year", "archive_year", "season_end"):
        candidate = context.get(key)
        if isinstance(candidate, int):
            return candidate
    return None


def apply_context_overrides(
    context: dict,
    *,
    year: int | None,
    stage_or_round: str,
    round_detail: str | None,
    document_type: str,
) -> tuple[int | None, str, str | None, str]:
    year = context_year(context) or year
    stage_or_round = str(context.get("stage_or_round") or stage_or_round)
    round_detail = str(context.get("round_detail") or round_detail or "") or None
    document_type = str(context.get("document_type") or document_type)
    return year, stage_or_round, round_detail, document_type


def append_note(notes: str, extra_note: str) -> str:
    if not extra_note or extra_note in notes:
        return notes
    if not notes:
        return extra_note
    return notes + f"; {extra_note}"


def page_has_problem_statements(page_text: str) -> bool:
    lowered = page_text.lower()
    first_problem = re.search(r"(?:^|\s)(?:1[.)]|problem\s*1)\s+\S", lowered)
    second_problem = re.search(r"(?:^|\s)(?:2[.)]|problem\s*2)\s+\S", lowered)
    return bool(first_problem and second_problem)


def is_html_container_page(raw_html: str, page_url: str, page_text: str) -> bool:
    lowered = page_text.lower()
    if "к сожалению, у нас нет заданий" in lowered:
        return True

    has_problem_statements = page_has_problem_statements(page_text)
    links = extract_links(raw_html, page_url)
    direct_file_links = [link for link in links if infer_extension(link["href"]) in DIRECT_FILE_EXTENSIONS]
    language_tokens = sum(
        token in lowered
        for token in (
            "english",
            "russian",
            "bulgarian",
            "swedish",
            "portugues",
            "armenian",
        )
    )

    if direct_file_links and not has_problem_statements:
        return True
    if language_tokens >= 2 and ("languages" in lowered or "not ready" in lowered) and not has_problem_statements:
        return True
    return False


def serbia_stage_from_url(url: str) -> str | None:
    filename = decoded_filename(url)
    for pattern, stage in SERBIA_ARCHIVE_PATTERNS:
        match = pattern.fullmatch(filename)
        if match:
            if int(match.group("year")) > CURRENT_YEAR:
                return None
            return stage
    return None


def should_record_seed_page(seed: dict) -> bool:
    context = seed_context(seed)
    if source_id_of(seed) in SKIP_SEED_PAGE_SOURCE_IDS:
        return False
    if context.get("container_only"):
        return False
    if context.get("record_seed_page") is False:
        return False
    return True


def is_russia_team_qual_direct_archive_file(url: str) -> bool:
    if not url.lower().startswith("https://astroedu.ru/assets/problems/hq/"):
        return False
    return infer_extension(url) in {"pdf", "zip"}


def is_vsosh_astroedu_archive_pdf(url: str) -> bool:
    return url.lower().startswith("https://astroedu.ru/assets/problems/vos/") and decoded_filename(url).lower().endswith(".pdf")


def is_current_vsosh_edsoo_document(link_text: str, url: str) -> bool:
    if "vso.edsoo.ru/public.php/dav/files/" not in url.lower():
        return False
    text = link_text.lower()
    short_year = str(CURRENT_YEAR)[-2:]
    season_tokens = (f"{CURRENT_YEAR - 1}/{short_year}", f"{CURRENT_YEAR - 1}-{short_year}", str(CURRENT_YEAR))
    if not any(token in text for token in season_tokens):
        return False
    if "астроном" in text:
        return True
    return any(
        phrase in text
        for phrase in (
            "приказ",
            "регламент заключительного этапа",
            "требования к организации и проведению регионального этапа",
        )
    )


def is_spbao_official_pdf(url: str) -> bool:
    return "system/files/" in url and url.lower().endswith(".pdf")


OWAO_ASTROEDU_MATERIAL_RE = re.compile(
    r"^/assets/problems/owao/(?P<path_year>20\d{2})/"
    r"OWAO-(?P<filename_year>20\d{2})-"
    r"(?:(?P<kind>prob|sol)-(?P<round>T|P)|P-files)\.(?P<extension>pdf|zip)$",
    flags=re.IGNORECASE,
)


def owao_astroedu_material_metadata(url: str) -> tuple[str, list[str], str, str] | None:
    """Infer OWAO metadata from direct files in the astroedu.ru archive."""
    if source_domain(url) != "astroedu.ru":
        return None
    match = OWAO_ASTROEDU_MATERIAL_RE.fullmatch(decoded_url_path(url))
    if not match or match.group("path_year") != match.group("filename_year"):
        return None
    extension = match.group("extension").lower()
    kind = match.group("kind")
    if kind is None:
        if extension != "zip":
            return None
        return "reference_data", ["reference_data"], "practical", "practical"
    if extension != "pdf":
        return None
    stage_or_round = "theoretical" if match.group("round").lower() == "t" else "practical"
    document_type = "tasks" if kind.lower() == "prob" else "solutions"
    return document_type, [document_type], stage_or_round, stage_or_round


def owao_page_links(raw_html: str, base_url: str) -> list[dict[str, str]]:
    """Return OWAO links with the nearest round heading as page context.

    The official pages group otherwise context-free share links under round headings.
    Keeping that context here avoids a broad HTML parser change for other sources.
    """
    links_by_text: dict[str, list[dict[str, str]]] = defaultdict(list)
    for link in extract_links(raw_html, base_url):
        links_by_text[link["text"]].append(link)
    current_section = ""
    current_year = infer_year(base_url)
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in OWAO_PAGE_TOKEN_RE.finditer(raw_html):
        label_contents = match.group("heading_text") or match.group("label_text")
        if label_contents is not None:
            text = html_to_text(label_contents).strip()
            heading_year = infer_year(text)
            if heading_year is not None:
                current_year = heading_year
            if "round" in text.lower():
                current_section = text
            # Tilda sometimes puts the Files-to-tasks anchor inside the positioned
            # text element itself, so the outer div token consumes that anchor.
            for link in extract_links(label_contents, base_url):
                key = (link["href"], link["text"])
                if key not in seen:
                    seen.add(key)
                    result.append({**link, "section": current_section, "year": current_year})
            continue
        text = html_to_text(match.group("anchor_text") or "").strip()
        # Resolve this anchor through the established extractor so URL handling stays shared.
        matching = links_by_text.get(text, [])
        if matching:
            # Anchors are processed in source order, as are extract_links results.
            link = matching.pop(0)
            key = (link["href"], text)
            if key in seen:
                continue
            seen.add(key)
            result.append({**link, "section": current_section, "year": current_year})
    return result


def owao_access_notes(url: str) -> str:
    domain = source_domain(url)
    notes = "official"
    if domain == "my.sirius.online":
        notes = append_note(notes, "host=my.sirius.online")
    elif domain == "nextcloud-storage.talantiuspeh.ru":
        notes = append_note(notes, "external_share=nextcloud")
    elif domain == "disk.yandex.ru":
        notes = append_note(notes, "external_share=yandex_disk")
    elif domain == "uts.astroedu.ru":
        notes = append_note(notes, "interactive_or_login=uts")
        notes = append_note(notes, "discovery_only")
    elif domain == "edu.sirius.online":
        notes = append_note(notes, "interactive_or_login=edu_sirius")
        notes = append_note(notes, "discovery_only")
    return notes


def czech_school_year(text: str) -> int | None:
    match = re.search(r"(20\d{2})[-/](\d{2})(?!\d)", text)
    if not match:
        return None
    first, suffix = int(match.group(1)), int(match.group(2))
    return (first // 100) * 100 + suffix + (100 if suffix <= first % 100 else 0)


def usaaao_event_year(href: str, context: dict) -> int | None:
    """WordPress upload dates are publication metadata, not competition years."""
    return infer_year(decoded_filename(href)) or context_year(context)


def batch_a_page_links(seed: dict, raw_html: str, base_url: str, page_context: dict) -> list[dict]:
    """Parse the five Batch A archives without broad domain crawling."""
    source_id = source_id_of(seed)
    parser = parsed_page(raw_html, base_url)
    if source_id in INAO_SOURCE_IDS:
        result = []
        for row in parser.rows:
            text = str(row["text"])
            if "inao" not in text.lower() and not re.search(r"\bastronomy\b", text, re.I):
                continue
            for link in row["links"]:
                if infer_extension(link["href"]) == "pdf":
                    result.append({**link, "context": {"year": infer_year(text) or context_year(page_context), "stage_or_round": "national", "round_detail": "junior" if re.search(r"\b(?:jr|junior)\b", text, re.I) else None}, "context_text": text})
        return result
    result, year, stage, detail, category = [], czech_school_year(base_url), "unknown", None, None
    for token in parser.tokens:
        if token["kind"] == "text":
            text, lowered = token["text"], token["text"].lower()
            # Czech edition year is immutable: navigation, prose dates and file
            # IDs must never replace the year parsed from the edition URL.
            if source_id != CZECH_SOURCE_ID:
                discovered_year = infer_year(text)
                if discovered_year is not None:
                    year = discovered_year
            if source_id == USAAAO_SOURCE_ID:
                if "first round" in lowered: stage, detail = "first-round", "theoretical"
                elif "practice round" in lowered: stage, detail = "practice", None
                elif re.search(r"\bnac\b", lowered): stage, detail = "national", "theoretical"
                elif "third exam" in lowered: stage, detail = "selection", "theoretical"
            elif source_id == CZECH_SOURCE_ID:
                if "školní kolo" in lowered: stage = "school"
                elif "krajské kolo" in lowered: stage = "regional"
                elif "ústřední kolo" in lowered or "finále" in lowered: stage = "final"
                match = re.search(r"kategorie\s*[-_:]?\s*(ab|cd|ef|gh)\b", lowered)
                if match: category = match.group(1).upper()
            continue
        href, text = token["href"], token["text"]
        if source_id == USAAAO_SOURCE_ID and "practical" in f"{text} {decoded_filename(href)}".lower():
            stage, detail = "selection", "practical"
        direct = infer_extension(href) == "pdf" or (source_id == CZECH_SOURCE_ID and "/f/detail/" in href)
        year_page = source_id == CZECH_SOURCE_ID and bool(re.search(r"/archiv/\d+-rocnik-20\d{2}-(?:\d{2}|20\d{2})/?$", href))
        if source_id == IOAA_JUNIOR_SOURCE_ID:
            year_page = bool(re.search(r"/junior-ioaa/past-olympiads/20\d{2}/?$", href))
            direct = infer_extension(href) == "pdf"
        if not (direct or year_page): continue
        # The archive contains news, international competitions, and other
        # non-AO material alongside the actual round/category blocks.  A
        # direct attachment belongs to Czech AO only while a recognized round
        # heading is active; category is intentionally optional for older
        # editions that do not label it.
        if source_id == CZECH_SOURCE_ID and direct and stage not in {"school", "regional", "final"}:
            continue
        link_year = usaaao_event_year(href, {"year": year}) if source_id == USAAAO_SOURCE_ID else year if source_id == CZECH_SOURCE_ID else infer_year(f"{href} {text}") or year
        link_context = {"year": link_year, "stage_or_round": stage, "round_detail": detail}
        if category: link_context["category"] = category
        result.append({"href": href, "text": text, "context": link_context, "context_text": f"Kategorie {category or ''} {text}"})
    return result


def access_mode_for_url(url: str) -> tuple[str, str]:
    """Interactive targets are useful provenance, but not crawl targets."""
    domain = source_domain(url)
    if domain == "uts.astroedu.ru":
        return "discovery_only", "interactive_or_login=uts"
    if domain == "edu.sirius.online":
        return "discovery_only", "interactive_or_login=edu_sirius"
    return "download", ""


def contextual_archive_links(raw_html: str, base_url: str, source_id: str) -> list[dict]:
    """Extract links plus nearby archive context for the three structured pages."""
    result: list[dict] = []
    anchor_re = re.compile(r"<a\b[^>]*href=(['\"])(.*?)\1[^>]*>(.*?)</a>", re.I | re.S)
    for match in anchor_re.finditer(raw_html):
        href = urljoin(base_url, match.group(2).strip())
        text = html_to_text(match.group(3)).strip()
        before = html_to_text(raw_html[: match.start()])
        context: dict = {}
        if source_id == STRUVE_ASTROEDU_SOURCE_ID:
            years = re.findall(r"(?:^|\s)(20\d{2})(?:\s|$)", before)
            if years:
                context["year"] = int(years[-1])
            section_start = raw_html.rfind("<h", 0, match.start())
            recent = html_to_text(raw_html[section_start:match.start()]).lower()
            if "региональ" in recent:
                context["stage_or_round"] = "regional"
            elif "заключитель" in recent:
                context["stage_or_round"] = "final"
            if "онлайн" in recent:
                context["round_detail"] = "online"
            elif "письмен" in recent:
                context["round_detail"] = "written"
            paragraph_start = raw_html.rfind("<p", section_start, match.start())
            paragraph = html_to_text(raw_html[paragraph_start:match.start()]).lower()
            day = re.search(r"день\s*([12])", paragraph)
            if day:
                context["round_detail"] = f"day{day.group(1)}"
            grade = re.search(r"(?:класс|grade)[ -]?(\d{1,2})", f"{recent} {text}".lower())
            if grade:
                context["grade"] = int(grade.group(1))
        elif source_id == "mao_official_archive":
            section_start = raw_html.rfind("<h", 0, match.start())
            recent = html_to_text(raw_html[section_start:match.start()]).lower()
            year = infer_year(before[-700:])
            if year:
                context["year"] = year
            stage_positions = {"distant": recent.rfind("дистанцион"), "theoretical": recent.rfind("теоретическ"), "observational": recent.rfind("наблюдатель")}
            stage, position = max(stage_positions.items(), key=lambda item: item[1])
            if position >= 0:
                context["stage_or_round"] = stage
        elif source_id == RUSSIA_TEAM_QUAL_SOURCE_ID:
            row_start = raw_html.rfind("<tr", 0, match.start())
            row_text = html_to_text(raw_html[row_start:match.start()]).lower()
            cell_start = raw_html.rfind("<td", row_start, match.start())
            cell_text = html_to_text(raw_html[cell_start:match.start()]).lower()
            series = re.search(r"\bq(\d{2})s\d+\b", row_text, re.I)
            if series:
                token = series.group(0).upper()
                context.update({"series": token, "year": 2000 + int(series.group(1)), "round_detail": token})
            label = f"{cell_text} {text}".lower()
            if "теорет" in label:
                context["stage_or_round"] = "theoretical"
            elif "практи" in label:
                context["stage_or_round"] = "practical"
            elif "наблюд" in label:
                context["stage_or_round"] = "observational"
            elif "блиц" in label:
                context["stage_or_round"] = "test"
                context["round_detail"] = f"blitz-{context.get('series', '')}".rstrip("-")
        result.append({"href": href, "text": text, "context": context})
    return result


def passes_source_specific_link_filter(seed: dict, link_text: str, href: str) -> bool:
    source_id = source_id_of(seed)
    combined = f"{link_text} {href}".lower()
    if source_id == STRUVE_SOURCE_ID:
        # The shared vos.olimpiada.ru year pages also contain broader VsOSH material,
        # so the Struve source keeps only Struve links and does not record the generic seed page.
        return "struve" in f"{link_text} {href}".lower()
    if source_id == RUSSIA_TEAM_QUAL_SOURCE_ID:
        return is_russia_team_qual_direct_archive_file(href) or source_domain(href) == "uts.astroedu.ru"
    if source_id == STRUVE_ASTROEDU_SOURCE_ID:
        return href.lower().startswith("https://astroedu.ru/assets/problems/struve/") or source_domain(href) == "uts.astroedu.ru"
    if source_id == OWAO_ASTROEDU_SOURCE_ID:
        return owao_astroedu_material_metadata(href) is not None
    if source_id == VSOSH_ASTROEDU_SOURCE_ID:
        return is_vsosh_astroedu_archive_pdf(href)
    if source_id == VSOSH_EDSOO_SOURCE_ID:
        return is_current_vsosh_edsoo_document(link_text, href)
    if source_id == SERBIA_SOURCE_ID:
        return serbia_stage_from_url(href) is not None
    if source_id in IOAA_CORE_SOURCE_IDS:
        return "gecaa" not in combined and "junior-ioaa" not in combined and "junior ioaa" not in combined
    if source_id == IOAA_JUNIOR_SOURCE_ID:
        return bool(re.search(r"/junior-ioaa/past-olympiads/20\d{2}/?$", href)) or (infer_extension(href) == "pdf" and bool(re.search(r"question|answer|solution|problem|paper", combined)))
    if source_id in {USAAAO_SOURCE_ID, *INAO_SOURCE_IDS}:
        return infer_extension(href) == "pdf"
    if source_id == CZECH_SOURCE_ID:
        if re.search(r"(?:^|[^a-z0-9])(?:iao|ioaa|vysledky|diplom|tz-ao|gallery|press|news)(?:$|[^a-z0-9])", combined):
            return False
        return "/f/detail/" in href or infer_extension(href) == "pdf" or bool(re.search(r"/archiv/\d+-rocnik-20\d{2}-(?:\d{2}|20\d{2})/?$", href))
    if source_id in GECAA_SOURCE_IDS:
        return infer_extension(href) == "pdf" and not bool(re.search(r"circular|regulation|result", combined)) and bool(re.search(r"theor|data[_ -]*analysis|observation|student[_ -]*user[_ -]*guide|team[_ -]*competition|moon|pixie", combined))
    return True


def should_record_seed_link(seed: dict, link_text: str, href: str) -> bool:
    source_id = source_id_of(seed)
    if source_id == VSOSH_MOSCOW_TEAM_SOURCE_ID:
        return False
    if source_id == VSOSH_SIRIUS_SOURCE_ID:
        return "протокол" in link_text.lower() and infer_extension(href) == "pdf"
    # Sources with query-string file URLs bypass the generic extension check
    if source_id == SPBAO_OFFICIAL_SOURCE_ID:
        return is_spbao_official_pdf(href)
    if source_id == VSOSH_EDSOO_SOURCE_ID:
        return is_current_vsosh_edsoo_document(link_text, href)
    if source_id == OWAO_SOURCE_ID:
        return bool(re.search(r"problems?|solutions?|files to the tasks|задани|решени", link_text, re.IGNORECASE))
    if source_id == CZECH_SOURCE_ID and ("/f/detail/" in href or "/archiv/" in href):
        return passes_source_specific_link_filter(seed, link_text, href)
    if source_id == IOAA_JUNIOR_SOURCE_ID and re.search(r"/junior-ioaa/past-olympiads/20\d{2}/?$", href):
        return True
    if source_id in {STRUVE_ASTROEDU_SOURCE_ID, RUSSIA_TEAM_QUAL_SOURCE_ID} and source_domain(href) == "uts.astroedu.ru":
        return passes_source_specific_link_filter(seed, link_text, href)
    if not should_record_link(href):
        return False
    return passes_source_specific_link_filter(seed, link_text, href)


def infer_family(default_family: str, *texts: str) -> str:
    if default_family in {"ioaa_junior", "gecaa", "usaaao", "inao", "czech_astronomy"}:
        return default_family
    text = " ".join(texts).lower()
    if "ioaa" in text or "gecaa" in text:
        return "ioaa"
    if default_family == "iao":
        return "iao"
    return default_family


def apply_source_specific_seed_page_overrides(seed: dict, document_type: str, extra_types: list[str]) -> tuple[str, list[str]]:
    if is_source_seed(seed, OWAO_SOURCE_ID):
        return "info", []
    return document_type, extra_types


def record_seed_page(seed: dict, title: str, extension: str = "html") -> dict:
    context = seed_context(seed)
    family = infer_family(seed["olympiad_family"], seed["url"], title)
    year = infer_year(f"{seed['url']} {title}")
    document_type, extra_types = infer_document_type(title, seed["url"], seed["source_id"])
    document_type, extra_types = apply_source_specific_seed_page_overrides(seed, document_type, extra_types)
    stage_or_round, round_detail = infer_stage(family, title, seed["url"])
    year, stage_or_round, round_detail, document_type = apply_context_overrides(
        context,
        year=year,
        stage_or_round=stage_or_round,
        round_detail=round_detail,
        document_type=document_type,
    )
    language = infer_language(title)
    variant_tag = infer_variant_tag(seed["source_role"], title or seed["source_id"], seed["url"], extra_types)
    return {
        "candidate_id": hashlib.sha1(seed["url"].encode("utf-8")).hexdigest(),
        "source_id": seed["source_id"],
        "olympiad_family": family,
        "year": year,
        "stage_or_round": stage_or_round,
        "language": language,
        "document_type": document_type,
        "source_url": seed["url"],
        "source_domain": source_domain(seed["url"]),
        "source_title": title,
        "source_priority": seed["source_priority"],
        "source_role": seed["source_role"],
        "parent_page_url": seed["url"],
        "parent_page_title": title,
        "filename_original": decoded_filename(seed["url"]) or "page.html",
        "extension": extension,
        "variant_tag": variant_tag,
        "round_detail": round_detail,
        "access_mode": "download",
        "notes": f"seed_page=true; source_kind=html; extra_types={','.join(extra_types)}",
        "seed_context": context,
        "confidence": confidence_score(year, stage_or_round, document_type, title),
    }


def apply_source_specific_link_overrides(
    seed: dict,
    href: str,
    link_text: str,
    page_title: str,
    document_type: str,
    extra_types: list[str],
    stage_or_round: str,
    round_detail: str | None,
    language: str,
) -> tuple[str, list[str], str, str | None, str]:
    source_id = source_id_of(seed)
    if source_id == SERBIA_SOURCE_ID:
        serbia_stage = serbia_stage_from_url(href)
        if serbia_stage is not None:
            return "solutions", ["tasks", "solutions"], serbia_stage, None, "sr"
    if source_id == RUSSIA_TEAM_QUAL_SOURCE_ID and is_russia_team_qual_direct_archive_file(href):
        return document_type, extra_types, stage_or_round, round_detail, language
    if source_id == OWAO_ASTROEDU_SOURCE_ID:
        metadata = owao_astroedu_material_metadata(href)
        if metadata is not None:
            document_type, extra_types, stage_or_round, round_detail = metadata
            return document_type, extra_types, stage_or_round, round_detail, "en"
    if source_id == STRUVE_ASTROEDU_SOURCE_ID:
        lowered_href = href.lower()
        if "-reg-" in lowered_href:
            stage_or_round = "regional"
        elif "-final-" in lowered_href:
            stage_or_round = "final"
        day = re.search(r"day[-_]?([12])", lowered_href)
        if day:
            round_detail = f"day{day.group(1)}"
        if "-reg-sol-" in href.lower():
            document_type, extra_types = "solutions", ["solutions"]
        elif "-reg-prob-" in href.lower() or "-final-prob-" in href.lower():
            document_type, extra_types = "tasks", ["tasks"]
        return document_type, extra_types, stage_or_round, round_detail, "ru"
    if source_id == "mao_official_archive":
        text = f"{href} {document_type}".lower()
        if "ans" in text and "tasks" not in extra_types:
            extra_types = sorted(set(extra_types) | {"tasks", "solutions"})
            document_type = "solutions"
    text = normalize_whitespace(f"{link_text} {decoded_filename(href)} {href} {page_title}").lower()
    if source_id == IOAA_JUNIOR_SOURCE_ID:
        if re.search(r"/junior-ioaa/past-olympiads/20(?:22|23)/?$", href):
            return "info", ["info"], "event-page", None, "en"
        normalized = re.sub(r"[_-]+", " ", text)
        document_type, extra_types = ("solutions", ["tasks", "solutions"]) if "questions and answers" in normalized else (("solutions", ["solutions"]) if "answer" in normalized or "solution" in normalized else ("tasks", ["tasks"]))
        return document_type, extra_types, "combined", "theoretical_and_observational", "en"
    if source_id == USAAAO_SOURCE_ID:
        if "syllabus" in text or "physical constants" in text:
            return "info", ["info"], "reference", None, "en"
        if re.search(r"practice[ _-]*round", text):
            document_type, extra_types = ("solutions", ["solutions"]) if "solution" in text else ("tasks", ["tasks"])
            return document_type, extra_types, "practice", None, "en"
        if "solution" in text or "answer sheet" in text: document_type, extra_types = "solutions", ["solutions"]
        elif "exam" in text or "test" in text: document_type, extra_types = "tasks", ["tasks"]
        return document_type, extra_types, stage_or_round, round_detail, "en"
    if source_id in INAO_SOURCE_IDS:
        link_identity = normalize_whitespace(f"{link_text} {decoded_filename(href)} {href}").lower()
        if "solution" in link_identity or "answer booklet" in link_identity: document_type, extra_types = "solutions", ["solutions"]
        elif re.search(r"\bqp\b|question paper", link_identity): document_type, extra_types = "tasks", ["tasks"]
        if re.search(r"q-s\.pdf$", link_identity): document_type, extra_types = "solutions", ["tasks", "solutions"]
        division = "senior" if re.search(r"inaosr", link_identity) else "junior" if re.search(r"inaojr", link_identity) else round_detail
        return document_type, extra_types, stage_or_round, division, "hi" if re.search(r"hindi|qp\s*\(h\)|[_-]h(?:indi)?[_-]", link_identity) else "en"
    if source_id == CZECH_SOURCE_ID:
        if "řešení" in text or "reseni" in text: document_type, extra_types = "solutions", ["solutions"]
        elif "zadání" in text or "zadani" in text: document_type, extra_types = "tasks", ["tasks"]
        if re.search(r"\bda\b|datov|data[_ -]*analysis", text): round_detail = "data_analysis"
        elif re.search(r"\bteo\b|teoret", text): round_detail = "theoretical"
        return document_type, extra_types, stage_or_round, round_detail, "cs"
    if source_id in GECAA_SOURCE_IDS:
        combined = bool(re.search(r"problems?[/ _-]*solutions|-(?:theoretical|data-analysis|observation)-solutions", text))
        document_type, extra_types = ("instructions", ["instructions"]) if re.search(r"student[_ -]*user[_ -]*guide", text) else (("solutions", ["tasks", "solutions"] if combined else ["solutions"]) if "solution" in text else ("tasks", ["tasks"]))
        stage_or_round, round_detail = ("team", "team") if "team" in text or "pixie" in text else (("data-analysis", "data_analysis") if "data" in text else (("observational", "observational") if "observation" in text else ("theoretical", "theoretical")))
        return document_type, extra_types, stage_or_round, round_detail, "en"
    return document_type, extra_types, stage_or_round, round_detail, language


def apply_owao_metadata(
    link_text: str, page_title: str, href: str, document_type: str, extra_types: list[str], stage_or_round: str, round_detail: str | None
) -> tuple[str, list[str], str, str | None]:
    text = f"{link_text} {page_title} {href}".lower()
    if "express round and observation round" in text:
        stage_or_round, round_detail = "observational", "express_and_observational"
    elif "express round" in text:
        stage_or_round, round_detail = "express", "express"
    elif "observation round" in text or "observational round" in text:
        stage_or_round, round_detail = "observational", "observational"
    elif "practical round" in text:
        stage_or_round, round_detail = "practical", "practical"
    elif "theoretical round" in text:
        stage_or_round, round_detail = "theoretical", "theoretical"

    link_lower = link_text.lower()
    if "files to the tasks" in link_lower:
        document_type, extra_types = "reference_data", ["reference_data"]
    elif "problems and solutions" in link_lower:
        document_type, extra_types = "solutions", ["tasks", "solutions"]
    elif re.search(r"\bproblems?\b|задани", link_lower):
        document_type, extra_types = "tasks", ["tasks"]
    elif re.search(r"\bsolutions?\b|решени", link_lower):
        document_type, extra_types = "solutions", ["solutions"]
    return document_type, extra_types, stage_or_round, round_detail


def build_candidate_entry(
    seed: dict,
    *,
    href: str,
    link_text: str,
    page_title: str,
    parent_page_url: str,
    parent_page_title: str,
    context: dict,
) -> dict:
    title_bits = [link_text, page_title, href]
    family = infer_family(seed["olympiad_family"], href, link_text, page_title)
    year = infer_year(" ".join(filter(None, title_bits)))
    document_type, extra_types = infer_document_type(*title_bits)
    stage_or_round, round_detail = infer_stage(family, *title_bits)
    language = infer_language(link_text, href)
    if source_id_of(seed) == OWAO_SOURCE_ID:
        document_type, extra_types, stage_or_round, round_detail = apply_owao_metadata(
            link_text, page_title, href, document_type, extra_types, stage_or_round, round_detail
        )
    document_type, extra_types, stage_or_round, round_detail, language = apply_source_specific_link_overrides(
        seed,
        href,
        link_text,
        page_title,
        document_type,
        extra_types,
        stage_or_round,
        round_detail,
        language,
    )
    year, stage_or_round, round_detail, document_type = apply_context_overrides(
        context,
        year=year,
        stage_or_round=stage_or_round,
        round_detail=round_detail,
        document_type=document_type,
    )
    # These filename/source rules are authoritative.  Reapply them after page
    # context because a parent page can describe a different division/round.
    if source_id_of(seed) in {STRUVE_ASTROEDU_SOURCE_ID, IOAA_JUNIOR_SOURCE_ID, USAAAO_SOURCE_ID, *INAO_SOURCE_IDS}:
        document_type, extra_types, stage_or_round, round_detail, language = apply_source_specific_link_overrides(
            seed, href, link_text, page_title, document_type, extra_types, stage_or_round, round_detail, language
        )
    variant_tag = infer_variant_tag(seed["source_role"], link_text or page_title, href, extra_types)
    access_mode, access_note = access_mode_for_url(href)
    notes = append_note(f"extra_types={','.join(extra_types)}", access_note)
    if access_mode == "discovery_only":
        notes = append_note(notes, "discovery_only")
    source_role, source_priority = seed["source_role"], seed["source_priority"]
    if family == "iao" and source_domain(href) in {"issp.ac.ru", "www.issp.ac.ru"}:
        source_role, source_priority = "official", 1
        notes = append_note(notes, f"discovered_via={seed['source_id']}")
    return {
        "candidate_id": hashlib.sha1(f"{seed['source_id']}::{href}".encode("utf-8")).hexdigest(),
        "source_id": seed["source_id"],
        "olympiad_family": family,
        "year": year,
        "stage_or_round": stage_or_round,
        "language": language,
        "document_type": document_type,
        "source_url": href,
        "source_domain": source_domain(href),
        "source_title": link_text or page_title,
        "source_priority": source_priority,
        "source_role": source_role,
        "parent_page_url": parent_page_url,
        "parent_page_title": parent_page_title,
        "filename_original": decoded_filename(href) or "download",
        "extension": "pdf" if source_id_of(seed) == VSOSH_EDSOO_SOURCE_ID or (source_id_of(seed) == CZECH_SOURCE_ID and "/f/detail/" in href) else infer_extension(href),
        "variant_tag": variant_tag,
        "round_detail": round_detail,
        "logical_document_types": list(dict.fromkeys(extra_types)),
        "redistribution_status": "explicit-no-redistribution" if source_id_of(seed) in INAO_SOURCE_IDS else "",
        "access_mode": access_mode,
        "notes": append_note(append_note(notes, owao_access_notes(href) if source_id_of(seed) == OWAO_SOURCE_ID else ""), "redistribution_status=explicit-no-redistribution" if source_id_of(seed) in INAO_SOURCE_IDS else ""),
        "seed_context": context,
        "confidence": confidence_score(year, stage_or_round, document_type, link_text or page_title),
    }


def store_discovered_entry(
    discovered: dict[tuple[str, str], dict],
    entry: dict,
    *,
    seen_from: str | None = None,
    extra_note: str | None = None,
) -> None:
    key = (entry["source_id"], entry["source_url"])
    if key not in discovered:
        discovered[key] = entry
    else:
        current = discovered[key]
        if current.get("year") is None and entry.get("year") is not None:
            current["year"] = entry["year"]
        if current.get("stage_or_round") == "unknown" and entry.get("stage_or_round") != "unknown":
            current["stage_or_round"] = entry["stage_or_round"]
        if not current.get("round_detail") and entry.get("round_detail"):
            current["round_detail"] = entry["round_detail"]
        if current.get("document_type") == "info" and entry.get("document_type") != "info":
            current["document_type"] = entry["document_type"]
        current["confidence"] = round(max(float(current.get("confidence", 0.0)), float(entry.get("confidence", 0.0))), 2)
        if not current.get("seed_context") and entry.get("seed_context"):
            current["seed_context"] = entry["seed_context"]
    if seen_from:
        discovered[key]["notes"] = append_note(discovered[key]["notes"], f"seen_from={seen_from}")
    if extra_note:
        discovered[key]["notes"] = append_note(discovered[key]["notes"], extra_note)


def should_follow_second_hop(seed: dict, *, depth: int, parent_is_container: bool) -> bool:
    context = seed_context(seed)
    if not context.get("follow_second_hop"):
        return False
    max_follow_depth = int(context.get("max_follow_depth", 0) or 0)
    if depth >= max_follow_depth:
        return False
    return depth == 0 or parent_is_container


def derive_child_context(parent_context: dict, entry: dict) -> dict:
    child_context = dict(parent_context)
    if context_year(child_context) is None and isinstance(entry.get("year"), int):
        child_context["year"] = entry["year"]
    if not child_context.get("stage_or_round") and entry.get("stage_or_round") not in {"", "unknown", None}:
        child_context["stage_or_round"] = entry["stage_or_round"]
    if not child_context.get("round_detail") and entry.get("round_detail"):
        child_context["round_detail"] = entry["round_detail"]
    return child_context


def discover_documents(root: Path, families: set[str] | None, dry_run: bool, limit: int | None) -> int:
    logger = configure_logger("discover_sources", root / "data" / "logs" / "crawl.log")
    errors_logger = configure_logger("discover_sources.errors", root / "data" / "logs" / "errors.log")
    if dry_run:
        logger.info("DISCOVERY dry_run: no manifests updated")
        return 0
    client = HttpClient(logger=logger, dry_run=dry_run)
    source_rows = build_source_candidates_csv(root, families)
    logger.info("SOURCE_CANDIDATES count=%s", len(source_rows))

    seeds = []
    for source in SOURCE_DEFINITIONS:
        if families and source.olympiad_family not in families:
            continue
        seeds.extend(seed.to_dict() for seed in iter_seed_requests(source))

    if limit is not None:
        seeds = seeds[:limit]

    discovered: dict[tuple[str, str], dict] = {}
    coverage: dict[tuple[str, int | None, str], set[str]] = defaultdict(set)

    # Stable public direct-file fallbacks cover intermittent archive pages.
    for source in SOURCE_DEFINITIONS:
        if families and source.olympiad_family not in families:
            continue
        for href in source.extras.get("direct_file_urls", []):
            seed = {"source_id": source.source_id, "olympiad_family": source.olympiad_family, "source_role": source.source_role, "source_priority": source.source_priority, "context": dict(source.extras.get("default_context", {}))}
            entry = build_candidate_entry(seed, href=href, link_text=decoded_filename(href), page_title=source.label, parent_page_url=source.seed_urls[0], parent_page_title=source.label, context=seed["context"])
            store_discovered_entry(discovered, entry, seen_from=source.seed_urls[0])
            coverage[(entry["olympiad_family"], entry["year"], entry["stage_or_round"])].update(logical_document_types(entry))

    for seed in seeds:
        logger.info("SEED start source_id=%s url=%s", seed["source_id"], seed["url"])
        try:
            response = client.fetch(seed["url"])
        except Exception as error:
            errors_logger.error("SEED failed source_id=%s url=%s error=%s", seed["source_id"], seed["url"], error)
            continue

        if response.status_code and response.status_code >= 400:
            errors_logger.error("SEED bad_status source_id=%s url=%s status=%s", seed["source_id"], seed["url"], response.status_code)
            continue

        title = extract_title(response.text)
        if should_record_seed_page(seed):
            seed_page_entry = record_seed_page(seed, title)
            store_discovered_entry(discovered, seed_page_entry)

        page_queue: list[tuple[str, str, str, dict, int]] = [
            (response.final_url, title, response.text, seed_context(seed), 0)
        ]
        visited_pages: set[str] = set()
        while page_queue:
            page_url, page_title, page_html, page_context, depth = page_queue.pop(0)
            if page_url in visited_pages:
                continue
            visited_pages.add(page_url)

            page_text = html_to_text(page_html)
            parent_is_container = is_html_container_page(page_html, page_url, page_text)
            if depth > 0 and parent_is_container:
                key = (seed["source_id"], page_url)
                if key in discovered:
                    discovered[key]["notes"] = append_note(discovered[key]["notes"], "html_container=true")

            source_id = source_id_of(seed)
            if source_id == OWAO_SOURCE_ID:
                links = owao_page_links(page_html, page_url)
            elif source_id in {IOAA_JUNIOR_SOURCE_ID, USAAAO_SOURCE_ID, *INAO_SOURCE_IDS, CZECH_SOURCE_ID}:
                links = batch_a_page_links(seed, page_html, page_url, page_context)
            elif source_id in {STRUVE_ASTROEDU_SOURCE_ID, "mao_official_archive", RUSSIA_TEAM_QUAL_SOURCE_ID}:
                links = contextual_archive_links(page_html, page_url, source_id)
            else:
                links = extract_links(page_html, page_url)
            for link in links:
                href = link["href"]
                if source_id_of(seed) == OWAO_SOURCE_ID and not link.get("section"):
                    continue
                if not should_record_seed_link(seed, link["text"], href):
                    continue

                link_page_title = page_title
                if source_id_of(seed) == OWAO_SOURCE_ID and link.get("section"):
                    link_page_title = f"{page_title} {link['section']}"
                link_context = dict(page_context)
                link_context.update(link.get("context") or {})
                if link.get("context_text"):
                    link_page_title = normalize_whitespace(f"{link_page_title} {link['context_text']}")
                    link_context["source_context_text"] = link["context_text"]
                if source_id_of(seed) == OWAO_SOURCE_ID and isinstance(link.get("year"), int):
                    link_context["year"] = link["year"]
                if source_id_of(seed) == OWAO_SOURCE_ID:
                    filename_year = infer_year(decoded_filename(href))
                    if filename_year is not None:
                        link_context["year"] = filename_year
                if source_id_of(seed) == OWAO_SOURCE_ID and context_year(link_context) is None:
                    owao_year = infer_year(f"{page_url} {link_page_title}")
                    if owao_year is not None:
                        link_context["year"] = owao_year
                entry = build_candidate_entry(
                    seed,
                    href=href,
                    link_text=link["text"],
                    page_title=link_page_title,
                    parent_page_url=page_url,
                    parent_page_title=page_title,
                    context=link_context,
                )
                store_discovered_entry(discovered, entry, seen_from=page_url)
                coverage[(entry["olympiad_family"], entry["year"], entry["stage_or_round"])].update(logical_document_types(entry))

                extension = "html" if re.search(r"/(?:junior-ioaa/past-olympiads/20\d{2}|archiv/\d+-rocnik-20\d{2}-(?:\d{2}|20\d{2}))/?$", href) else infer_extension(href)
                if extension not in {"html", "htm"}:
                    continue
                if not should_follow_second_hop(seed, depth=depth, parent_is_container=parent_is_container):
                    continue
                try:
                    nested_response = client.fetch(href)
                except Exception as error:
                    errors_logger.error("FOLLOW failed source_id=%s url=%s error=%s", seed["source_id"], href, error)
                    continue
                if nested_response.status_code and nested_response.status_code >= 400:
                    errors_logger.error(
                        "FOLLOW bad_status source_id=%s url=%s status=%s",
                        seed["source_id"],
                        href,
                        nested_response.status_code,
                    )
                    continue
                nested_title = extract_title(nested_response.text)
                child_context = derive_child_context(page_context, entry)
                page_queue.append((nested_response.final_url, nested_title, nested_response.text, child_context, depth + 1))

    discovered_rows = sorted(
        discovered.values(),
        key=lambda row: (
            row["olympiad_family"],
            row["year"] or 0,
            row["stage_or_round"],
            row["document_type"],
            row["source_url"],
        ),
    )
    write_jsonl(root / "data" / "manifests" / "discovered_documents.jsonl", discovered_rows)

    coverage_rows = []
    for (family, year, stage), doc_types in sorted(
        coverage.items(),
        key=lambda item: (item[0][0], item[0][1] or 0, item[0][2]),
    ):
        coverage_rows.append(
            {
                "olympiad_family": family,
                "year": year,
                "stage_or_round": stage,
                "document_types_found": ",".join(sorted(doc_types)),
                "num_document_types": len(doc_types),
            }
        )

    coverage_path = root / "data" / "manifests" / "discovery_coverage.csv"
    ensure_dir(coverage_path.parent)
    with coverage_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(coverage_rows[0].keys()) if coverage_rows else [])
        if coverage_rows:
            writer.writeheader()
            writer.writerows(coverage_rows)

    logger.info("DISCOVERY done count=%s", len(discovered_rows))
    return 0


def main() -> int:
    parser = build_common_parser("Discover public astronomy olympiad sources and candidate documents.")
    args = parser.parse_args()
    families = set(args.families) if args.families else None
    return discover_documents(args.root, families, args.dry_run, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
