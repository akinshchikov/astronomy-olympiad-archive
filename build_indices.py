from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from utils.cli import build_common_parser
from utils.fs_utils import load_jsonl
from utils.logging_utils import configure_logger
from utils.metadata import PRIORITY_FAMILIES, logical_document_types


VSOSH_2026_CORE_COMPONENTS = (
    ("regional", "day-1", "Regional day 1"),
    ("regional", "day-2", "Regional day 2"),
    ("final", "theoretical", "Final theoretical"),
    ("final", "practical", "Final practical"),
    ("final", "test", "Final test/blitz"),
)
VSOSH_2026_GRADES = ("9", "10", "11")
VSOSH_2026_DOCUMENT_TYPES = ("tasks", "solutions")


def load_family_history(root: Path) -> dict[str, dict]:
    """Load and validate the conservative chronology configuration."""
    path = root / "data" / "config" / "family_history.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("family_history.json must contain an object")
    for family, history in payload.items():
        if not isinstance(history, dict) or not isinstance(history.get("first_competition_year"), int):
            raise ValueError(f"family history for {family} requires integer first_competition_year")
        for key in ("prehistory_or_anomalous_years", "known_not_held_years"):
            if not isinstance(history.get(key, []), list) or not all(isinstance(year, int) for year in history.get(key, [])):
                raise ValueError(f"family history for {family} has invalid {key}")
        for component in history.get("not_held_components", []):
            if not isinstance(component, dict) or not isinstance(component.get("year"), int) or not component.get("stage_or_round"):
                raise ValueError(f"family history for {family} has invalid not_held_components")
    return payload


def vsosh_2026_material_key(row: dict) -> tuple[str, str, str, str] | None:
    if row.get("olympiad_family") != "vsosh_astronomy" or row.get("year") != 2026:
        return None
    document_type = str(row.get("document_type", ""))
    if document_type not in VSOSH_2026_DOCUMENT_TYPES:
        return None

    text = " ".join(
        str(row.get(key, ""))
        for key in ("filename_original", "source_title", "source_url")
    ).lower()
    grade_match = re.search(r"(?:[-_ ])(9|10|11)(?:\.pdf|\b)", text)
    if not grade_match:
        return None

    stage = str(row.get("stage_or_round", ""))
    if stage == "regional":
        day_match = re.search(r"\bday[-_ ]?([12])\b", text)
        if not day_match:
            return None
        component = f"day-{day_match.group(1)}"
    elif stage == "final":
        component = str(row.get("round_detail") or "")
        if component not in {"theoretical", "practical", "test"}:
            return None
    else:
        return None

    return stage, component, document_type, grade_match.group(1)


def write_vsosh_2026_discovery_coverage(handle, discovered_rows: list[dict]) -> None:
    rows = [
        row
        for row in discovered_rows
        if row.get("olympiad_family") == "vsosh_astronomy" and row.get("year") == 2026
    ]
    found: set[tuple[str, str, str, str]] = set()
    for row in rows:
        key = vsosh_2026_material_key(row)
        if key:
            found.add(key)

    handle.write("### 2026 discovery coverage\n\n")
    handle.write("| Component | Found | Status |\n")
    handle.write("| --- | --- | --- |\n")
    complete_components = 0
    for stage, component, label in VSOSH_2026_CORE_COMPONENTS:
        expected = {
            (stage, component, document_type, grade)
            for document_type in VSOSH_2026_DOCUMENT_TYPES
            for grade in VSOSH_2026_GRADES
        }
        present = found & expected
        status = "complete" if present == expected else ("partial" if present else "missing")
        if status == "complete":
            complete_components += 1
        found_parts = []
        for document_type in VSOSH_2026_DOCUMENT_TYPES:
            grades = [
                grade
                for grade in VSOSH_2026_GRADES
                if (stage, component, document_type, grade) in present
            ]
            found_parts.append(f"{document_type}: {','.join(grades) or 'none'}")
        handle.write(f"| {label} | {'; '.join(found_parts)} | {status} |\n")

    reference_found = any(row.get("document_type") == "reference_data" for row in rows)
    official_types_by_stage = defaultdict(set)
    for row in rows:
        if row.get("source_id") != "vsosh_edsoo_stage_documents":
            continue
        if row.get("document_type") in {"requirements", "regulations", "order"}:
            official_types_by_stage[str(row.get("stage_or_round", "unknown"))].add(row["document_type"])
    official_parts = [
        f"{stage}: {','.join(sorted(document_types))}"
        for stage, document_types in sorted(official_types_by_stage.items())
    ]
    result_types = sorted(
        {
            str(row.get("document_type"))
            for row in rows
            if row.get("stage_or_round") == "final"
            and row.get("document_type") in {"results", "protocol"}
        }
    )
    handle.write(
        f"| Reference data | {'reference_data' if reference_found else 'none'} | "
        f"{'complete' if reference_found else 'missing'} |\n"
    )
    official_status = (
        "complete"
        if all("requirements" in official_types_by_stage[stage] for stage in ("regional", "final"))
        else ("partial" if official_parts else "missing")
    )
    handle.write(
        f"| Official requirements/orders | {'; '.join(official_parts) or 'none'} | "
        f"{official_status} |\n"
    )
    results_status = (
        "complete"
        if {"results", "protocol"} <= set(result_types)
        else ("partial" if result_types else "missing")
    )
    handle.write(
        f"| Results/protocols | {','.join(result_types) or 'none'} | "
        f"{results_status} |\n"
    )
    overall = "complete" if complete_components == len(VSOSH_2026_CORE_COMPONENTS) else "partial"
    handle.write(
        f"\n- Core tasks/solutions: {overall} "
        f"({complete_components}/{len(VSOSH_2026_CORE_COMPONENTS)} components complete).\n"
    )
    handle.write("- Status is based on discovered public sources; downloading is tracked separately below.\n\n")


def build(root: Path, families: set[str] | None) -> int:
    logger = configure_logger("build_indices", root / "data" / "logs" / "normalization.log")
    entries = load_jsonl(root / "data" / "manifests" / "normalized_entries.jsonl")
    discovered_rows = load_jsonl(root / "data" / "manifests" / "discovered_documents.jsonl")
    downloaded_rows = load_jsonl(root / "data" / "manifests" / "download_manifest.jsonl")
    if families:
        entries = [row for row in entries if row["olympiad_family"] in families]
        discovered_rows = [row for row in discovered_rows if row["olympiad_family"] in families]
        downloaded_rows = [row for row in downloaded_rows if row["olympiad_family"] in families]

    relation_groups_lookup = {}
    relation_groups_path = root / "data" / "indices" / "relation_groups.csv"
    if relation_groups_path.exists():
        with relation_groups_path.open("r", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                relation_groups_lookup[row["relation_group_id"]] = row

    objects: dict[str, dict] = {}
    olympiad_index: dict[tuple[str, int | None, str], dict] = {}
    relation_groups_per_event: dict[tuple[str, int | None, str], set[str]] = defaultdict(set)
    downloaded_candidate_ids = {row["candidate_id"] for row in downloaded_rows}
    missing_rows_by_family: dict[str, list[dict]] = defaultdict(list)
    for row in discovered_rows:
        if row["candidate_id"] not in downloaded_candidate_ids:
            missing_rows_by_family[row["olympiad_family"]].append(row)

    for entry in entries:
        objects.setdefault(
            entry["sha256"],
            {
                "sha256": entry["sha256"],
                "object_path": entry["object_path"],
                "extension": entry["extension"],
                "file_size": entry["file_size"],
                "representative_filename": entry["filename_normalized"],
                "source_count": 0,
                "source_urls": set(),
                "olympiad_family": entry["olympiad_family"],
                "year": entry["year"],
                "stage_or_round": entry["stage_or_round"],
                "document_type": entry["document_type"],
                "language": entry["language"],
            },
        )
        objects[entry["sha256"]]["source_count"] += 1
        objects[entry["sha256"]]["source_urls"].add(entry["source_url"])

        key = (entry["olympiad_family"], entry["year"], entry["stage_or_round"])
        if key not in olympiad_index:
            olympiad_index[key] = {
                "olympiad_family": entry["olympiad_family"],
                "year": entry["year"],
                "stage_or_round": entry["stage_or_round"],
                "has_tasks": False,
                "has_solutions": False,
                "has_marking": False,
                "has_analysis": False,
                "num_files": 0,
                "num_relation_groups": 0,
                "source_count": 0,
                "confidence": 0.0,
            }

        olympiad_index[key]["num_files"] += 1
        olympiad_index[key]["source_count"] += 1
        olympiad_index[key]["confidence"] = round(
            max(olympiad_index[key]["confidence"], float(entry.get("confidence", 0.0))),
            2,
        )
        entry_types = logical_document_types(entry)
        olympiad_index[key]["has_tasks"] = olympiad_index[key]["has_tasks"] or "tasks" in entry_types
        olympiad_index[key]["has_solutions"] = olympiad_index[key]["has_solutions"] or "solutions" in entry_types
        olympiad_index[key]["has_marking"] = olympiad_index[key]["has_marking"] or "marking" in entry_types
        olympiad_index[key]["has_analysis"] = olympiad_index[key]["has_analysis"] or "analysis" in entry_types

        if entry.get("relation_group_id"):
            relation_groups_per_event[key].add(entry["relation_group_id"])

    # Discovery-only sources still represent known event coverage.  Keep them in
    # the lightweight event index even when robots, login requirements, or an
    # external share prevent lawful automatic normalization.
    for row in discovered_rows:
        key = (row["olympiad_family"], row["year"], row["stage_or_round"])
        if key not in olympiad_index:
            olympiad_index[key] = {
                "olympiad_family": row["olympiad_family"],
                "year": row["year"],
                "stage_or_round": row["stage_or_round"],
                "has_tasks": False,
                "has_solutions": False,
                "has_marking": False,
                "has_analysis": False,
                "num_files": 0,
                "num_relation_groups": 0,
                "source_count": 0,
                "confidence": 0.0,
            }
        payload = olympiad_index[key]
        discovered_types = logical_document_types(row)
        payload["has_tasks"] = payload["has_tasks"] or "tasks" in discovered_types
        payload["has_solutions"] = payload["has_solutions"] or "solutions" in discovered_types
        payload["has_marking"] = payload["has_marking"] or "marking" in discovered_types
        payload["has_analysis"] = payload["has_analysis"] or "analysis" in discovered_types
        payload["confidence"] = round(max(payload["confidence"], float(row.get("confidence", 0.0))), 2)

    for key, group_ids in relation_groups_per_event.items():
        olympiad_index[key]["num_relation_groups"] = len(group_ids)

    files_index_path = root / "data" / "indices" / "files_index.csv"
    files_index_path.parent.mkdir(parents=True, exist_ok=True)
    files_rows = []
    for payload in objects.values():
        object_path = Path(payload["object_path"])
        try:
            object_path_value = str(object_path.relative_to(root))
        except ValueError:
            object_path_value = str(object_path)
        files_rows.append(
            {
                **payload,
                "object_path": object_path_value,
                "source_urls": "|".join(sorted(payload["source_urls"])),
            }
        )
    with files_index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(files_rows[0].keys()) if files_rows else [])
        if files_rows:
            writer.writeheader()
            writer.writerows(sorted(files_rows, key=lambda row: (row["olympiad_family"], row["year"] or 0, row["representative_filename"])))

    olympiads_index_path = root / "data" / "indices" / "olympiads_index.csv"
    with olympiads_index_path.open("w", encoding="utf-8", newline="") as handle:
        rows = sorted(olympiad_index.values(), key=lambda row: (row["olympiad_family"], row["year"] or 0, row["stage_or_round"]))
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    coverage_path = root / "data" / "indices" / "coverage_report.md"
    with coverage_path.open("w", encoding="utf-8") as handle:
        handle.write("# Coverage Report\n\n")
        by_family = defaultdict(list)
        for row in sorted(olympiad_index.values(), key=lambda row: (row["olympiad_family"], row["year"] or 0, row["stage_or_round"])):
            by_family[row["olympiad_family"]].append(row)

        entries_by_family = defaultdict(list)
        for entry in entries:
            entries_by_family[entry["olympiad_family"]].append(entry)

        if families:
            coverage_families = [family for family in PRIORITY_FAMILIES if family in families]
            coverage_families.extend(sorted(families - set(PRIORITY_FAMILIES)))
        else:
            coverage_families = PRIORITY_FAMILIES

        family_history = load_family_history(root)
        for family in coverage_families:
            family_rows = by_family.get(family, [])
            handle.write(f"## {family}\n\n")
            if family == "vsosh_astronomy":
                write_vsosh_2026_discovery_coverage(handle, discovered_rows)
            if not family_rows:
                handle.write("- No materials discovered yet.\n\n")
                continue

            years = sorted({row["year"] for row in family_rows if row["year"] is not None})
            tasks_years = sorted({row["year"] for row in family_rows if row["has_tasks"] and row["year"] is not None})
            solutions_years = sorted(
                {row["year"] for row in family_rows if row["has_solutions"] and row["year"] is not None}
            )
            mirror_only = sorted(
                {
                    entry["year"]
                    for entry in entries_by_family[family]
                    if entry["source_role"] == "mirror"
                    and entry["year"] is not None
                }
            )
            low_conf = sorted(
                {
                    entry["year"]
                    for entry in entries_by_family[family]
                    if float(entry.get("confidence", 0.0)) < 0.75 and entry["year"] is not None
                }
            )
            relation_counts = Counter(
                entry["relation_type"]
                for entry in entries_by_family[family]
                if entry.get("relation_type")
            )
            missing_rows = missing_rows_by_family.get(family, [])
            missing_years = sorted({row["year"] for row in missing_rows if row["year"] is not None})
            missing_by_doc = Counter(row["document_type"] for row in missing_rows)

            handle.write(f"- Years found: {', '.join(map(str, years))}\n")
            handle.write(f"- Years with tasks: {', '.join(map(str, tasks_years)) or 'none'}\n")
            handle.write(f"- Years with solutions: {', '.join(map(str, solutions_years))}\n")
            handle.write(f"- Years with mirror material: {', '.join(map(str, mirror_only)) or 'none'}\n")
            handle.write(
                "- Relation groups summary: "
                + (", ".join(f"{name}={count}" for name, count in sorted(relation_counts.items())) or "none")
                + "\n"
            )
            handle.write(f"- Low-confidence years: {', '.join(map(str, low_conf)) or 'none'}\n")
            handle.write(
                "- Discovery-only / undownloaded years: "
                + (", ".join(map(str, missing_years)) if missing_years else "none")
                + "\n"
            )
            handle.write(
                "- Undownloaded document types: "
                + (", ".join(f"{doc_type}={count}" for doc_type, count in sorted(missing_by_doc.items())) or "none")
                + "\n"
            )

            history = family_history.get(family, {})
            first_year = history.get("first_competition_year")
            prehistory = sorted(year for year in years if first_year is not None and year < first_year)
            valid_years = [year for year in years if first_year is None or year >= first_year]
            missing = []
            if valid_years:
                for year in range(max(min(valid_years), first_year or min(valid_years)), max(valid_years) + 1):
                    if year not in valid_years:
                        missing.append(str(year))
            handle.write(f"- Gaps: {', '.join(missing) or 'none observed inside valid competition range'}\n")
            if prehistory:
                handle.write(f"- Prehistory/anomalous years retained: {', '.join(map(str, prehistory))}\n")
            not_held = history.get("not_held_components", [])
            if not_held:
                rendered = "; ".join(f"{item['year']} {item['stage_or_round']} ({item['reason']})" for item in not_held)
                handle.write(f"- Known not-held components: {rendered}\n")
            handle.write("\n")

    logger.info("INDICES files=%s olympiad_rows=%s", len(files_rows), len(olympiad_index))
    return 0


def main() -> int:
    parser = build_common_parser("Build indices and coverage report from normalized archive.")
    args = parser.parse_args()
    families = set(args.families) if args.families else None
    return build(args.root, families)


if __name__ == "__main__":
    raise SystemExit(main())
