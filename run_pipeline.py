from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path

import build_indices
import cleanup_outputs
import crawl_source
import detect_relations
import discover_sources
import import_manual_files
import normalize_archive


PUBLIC_SNAPSHOT_FILES = (
    "data/manifests/source_candidates.csv",
    "data/manifests/discovered_documents.jsonl",
    "data/manifests/discovery_coverage.csv",
    "data/indices/olympiads_index.csv",
    "data/indices/files_index.csv",
    "data/indices/relation_groups.csv",
    "data/indices/coverage_report.md",
)


@contextmanager
def preserve_public_snapshot(root: Path, enabled: bool):
    """Keep focused runs from replacing the repository-wide public snapshot."""
    if not enabled:
        yield
        return

    snapshot: dict[str, bytes | None] = {}
    for relative in PUBLIC_SNAPSHOT_FILES:
        path = root / relative
        snapshot[relative] = path.read_bytes() if path.exists() else None

    try:
        yield
    finally:
        for relative, payload in snapshot.items():
            path = root / relative
            if payload is None:
                path.unlink(missing_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full archive pipeline.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--families", nargs="*", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--discover-limit", type=int, default=None)
    parser.add_argument("--download-limit", type=int, default=None)
    parser.add_argument("--clean", action="store_true", help="Remove generated outputs before running.")
    parser.add_argument("--clean-only", action="store_true", help="Remove generated outputs and exit.")
    args = parser.parse_args()

    families = set(args.families) if args.families else None

    # A family-scoped run is a local acquisition/validation operation. It may
    # rebuild partial manifests and indices internally, but it must not replace
    # the committed repository-wide snapshot that other users consume.
    with preserve_public_snapshot(args.root, enabled=bool(families)):
        if args.clean or args.clean_only:
            cleanup_outputs.clean_outputs(args.root, families)
            if args.clean_only:
                return 0

        discover_sources.discover_documents(args.root, families, args.dry_run, args.discover_limit)
        if args.dry_run:
            return 0
        crawl_source.crawl_documents(args.root, families, args.dry_run, args.download_limit)
        import_manual_files.import_manual_files(args.root, families)
        normalize_archive.normalize(args.root, families, args.dry_run, None)
        detect_relations.detect(args.root, families)
        build_indices.build(args.root, families)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
