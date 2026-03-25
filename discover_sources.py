from __future__ import annotations

import csv
import hashlib
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from utils.cli import build_common_parser
from utils.fs_utils import ensure_dir, write_jsonl
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
    infer_stage,
    infer_variant_tag,
    infer_year,
    source_domain,
)
from utils.source_configs import SOURCE_DEFINITIONS, iter_seed_requests


ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "zip", "html", "htm"}
DIRECT_FILE_EXTENSIONS = {"pdf", "doc", "docx", "zip"}
STRUVE_SOURCE_ID = "struve_moscow_year_pages"
OWAO_SOURCE_ID = "owao_tasks_official"
SERBIA_SOURCE_ID = "serbia_astronomy_official"
RUSSIA_TEAM_QUAL_SOURCE_ID = "russia_team_qual_archive"
VSOSH_ASTROEDU_SOURCE_ID = "vsosh_astroedu_archive"
SPBAO_OFFICIAL_SOURCE_ID = "spbao_official"
SKIP_SEED_PAGE_SOURCE_IDS = {STRUVE_SOURCE_ID}
CURRENT_YEAR = datetime.now().year
SERBIA_ARCHIVE_PATTERNS = (
    (re.compile(r"^OpstCont(?P<year>\d{4})\.pdf$", flags=re.IGNORECASE), "qualifying"),
    (re.compile(r"^RegioCont(?P<year>\d{4})\.pdf$", flags=re.IGNORECASE), "regional"),
    (re.compile(r"^RepubCont(?P<year>\d{4})\.pdf$", flags=re.IGNORECASE), "final"),
)


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


def is_spbao_official_pdf(url: str) -> bool:
    return "system/files/" in url and url.lower().endswith(".pdf")


def passes_source_specific_link_filter(seed: dict, link_text: str, href: str) -> bool:
    source_id = source_id_of(seed)
    if source_id == STRUVE_SOURCE_ID:
        # The shared vos.olimpiada.ru year pages also contain broader VsOSH material,
        # so the Struve source keeps only Struve links and does not record the generic seed page.
        return "struve" in f"{link_text} {href}".lower()
    if source_id == RUSSIA_TEAM_QUAL_SOURCE_ID:
        return is_russia_team_qual_direct_archive_file(href)
    if source_id == VSOSH_ASTROEDU_SOURCE_ID:
        return is_vsosh_astroedu_archive_pdf(href)
    if source_id == SERBIA_SOURCE_ID:
        return serbia_stage_from_url(href) is not None
    return True


def should_record_seed_link(seed: dict, link_text: str, href: str) -> bool:
    source_id = source_id_of(seed)
    # Sources with query-string file URLs bypass the generic extension check
    if source_id == SPBAO_OFFICIAL_SOURCE_ID:
        return is_spbao_official_pdf(href)
    if not should_record_link(href):
        return False
    return passes_source_specific_link_filter(seed, link_text, href)


def infer_family(default_family: str, *texts: str) -> str:
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
        "notes": f"seed_page=true; source_kind=html; extra_types={','.join(extra_types)}",
        "seed_context": context,
        "confidence": confidence_score(year, stage_or_round, document_type, title),
    }


def apply_source_specific_link_overrides(
    seed: dict,
    href: str,
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
        return document_type, extra_types, "qualifying", round_detail, language
    return document_type, extra_types, stage_or_round, round_detail, language


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
    document_type, extra_types, stage_or_round, round_detail, language = apply_source_specific_link_overrides(
        seed,
        href,
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
    variant_tag = infer_variant_tag(seed["source_role"], link_text or page_title, href, extra_types)
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
        "source_priority": seed["source_priority"],
        "source_role": seed["source_role"],
        "parent_page_url": parent_page_url,
        "parent_page_title": parent_page_title,
        "filename_original": decoded_filename(href) or "download",
        "extension": infer_extension(href),
        "variant_tag": variant_tag,
        "round_detail": round_detail,
        "notes": f"extra_types={','.join(extra_types)}",
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

            links = extract_links(page_html, page_url)
            for link in links:
                href = link["href"]
                if not should_record_seed_link(seed, link["text"], href):
                    continue

                entry = build_candidate_entry(
                    seed,
                    href=href,
                    link_text=link["text"],
                    page_title=page_title,
                    parent_page_url=page_url,
                    parent_page_title=page_title,
                    context=page_context,
                )
                store_discovered_entry(discovered, entry, seen_from=page_url)
                coverage[(entry["olympiad_family"], entry["year"], entry["stage_or_round"])].add(entry["document_type"])

                if infer_extension(href) not in {"html", "htm"}:
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
