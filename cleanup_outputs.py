from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from utils.metadata import path_slug
from utils.source_configs import SOURCE_DEFINITIONS

GENERATED_MANIFEST_FILES = (
    "source_candidates.csv",
    "discovered_documents.jsonl",
    "discovery_coverage.csv",
    "download_manifest.jsonl",
    "normalized_entries.jsonl",
    "relation_edges.jsonl",
)
GENERATED_INDEX_FILES = (
    "olympiads_index.csv",
    "files_index.csv",
    "relation_groups.csv",
    "coverage_report.md",
)


def remove_path(path: Path, removed: list[str]) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    removed.append(str(path))


def source_ids_for_families(families: set[str]) -> set[str]:
    return {
        source.source_id
        for source in SOURCE_DEFINITIONS
        if source.olympiad_family in families
    }


def clean_outputs(root: Path, families: set[str] | None) -> list[str]:
    removed: list[str] = []

    if families:
        for source_id in sorted(source_ids_for_families(families)):
            remove_path(root / "data" / "raw" / source_id, removed)
        for family in sorted(families):
            remove_path(root / "data" / "archive" / path_slug(family, fallback="olympiad"), removed)
        remove_path(root / "data" / "logs", removed)
        return removed

    remove_path(root / "data" / "raw", removed)
    remove_path(root / "data" / "archive", removed)
    remove_path(root / "data" / "logs", removed)

    for filename in GENERATED_MANIFEST_FILES:
        remove_path(root / "data" / "manifests" / filename, removed)
    for filename in GENERATED_INDEX_FILES:
        remove_path(root / "data" / "indices" / filename, removed)

    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove generated local pipeline outputs.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--families", nargs="*", default=None)
    args = parser.parse_args()

    families = set(args.families) if args.families else None
    removed = clean_outputs(args.root, families)
    scope = f"families={','.join(sorted(families))}" if families else "full"
    print(f"Removed {len(removed)} paths ({scope}).")
    for path in removed:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
