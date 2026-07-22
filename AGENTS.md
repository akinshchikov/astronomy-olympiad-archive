# AGENTS.md

## Project purpose

This repository is a reproducible local archive builder for publicly available astronomy olympiad materials. The public GitHub repo is intentionally `code + lightweight metadata`, not a mirror of downloaded binaries.

Priority families, in order:

1. `vsosh_astronomy`
2. `struve`
3. `owao`
4. `serbia_astronomy`
5. `russia_team_qual`
6. `spbao`
7. `mao`
8. `iao`
9. `ioaa`

## Repository layout

Core pipeline stages:

- `discover_sources.py` — discover candidate public documents from configured source seeds.
- `crawl_source.py` — download discovered documents into local raw storage.
- `normalize_archive.py` — normalize downloaded files into the local archive layout and object store.
- `detect_relations.py` — group related/duplicate variants.
- `build_indices.py` — build committed lightweight indices.
- `run_pipeline.py` — orchestrate the full pipeline.
- `cleanup_outputs.py` — remove generated local outputs.

Shared helpers live in `utils/`. Tests live in `tests/`.

Committed lightweight data:

- `data/manifests/source_candidates.csv`
- `data/manifests/discovered_documents.jsonl`
- `data/manifests/discovery_coverage.csv`
- `data/indices/olympiads_index.csv`
- `data/indices/files_index.csv`
- `data/indices/relation_groups.csv`
- `data/indices/coverage_report.md`

Never commit generated local binary/archive data:

- `data/raw/`
- `data/archive/`
- `data/logs/`
- `data/manifests/download_manifest.jsonl`
- `data/manifests/normalized_entries.jsonl`
- `data/manifests/relation_edges.jsonl`

## Development environment

- Target Python: `>=3.12`.
- Keep runtime dependencies minimal; `pyproject.toml` currently declares no third-party runtime dependencies.
- Prefer the standard library unless a new dependency is clearly justified.
- Keep the project runnable as simple scripts from the repository root.

Useful commands:

```bash
python3 -m pytest -q
python3 run_pipeline.py --dry-run
python3 run_pipeline.py --families spbao --discover-limit 20 --download-limit 20
python3 run_pipeline.py --clean --families spbao
python3 cleanup_outputs.py --families spbao
```

Do not run the full crawler or full clean rebuild unless explicitly requested. Prefer a focused family and small limits while developing.

## Safety and data-handling rules

- Respect `robots.txt` and existing crawler behavior. Do not add bypasses, scraping tricks, login flows, or anti-bot circumvention.
- Use only public URLs.
- Do not commit mirrored PDFs, archives, images, HTML dumps, or raw downloaded files.
- Do not treat public availability of a file as permission to redistribute the binary through GitHub.
- Keep `PUBLISHING.md` as the source of truth for what belongs in the public repository.
- Be careful with commands using `--clean`: they intentionally delete generated local outputs.

## Metadata and filename conventions

Preserve the normalized filename scheme:

```text
<year|unknown-year>--<olympiad-family>--<stage-or-round>--<document-type>--<lang>--<descriptor-1>[--<descriptor-2>...]--<variant-tag>.<ext>
```

Prefer meaningful descriptor tags such as:

- grades: `grade-10`, `grade-10-11`
- round/material tracks: `theory`, `practical`, `test`, `blitz`
- stages: `school`, `municipal`, `regional`, `final`, `selection`
- material kinds: `reference-data`, `questions`, `exam`, `problem-sheet`, `tasks-page`

Use fallback variant suffixes such as `-v2` only for genuinely distinct variants of the same package.

When improving metadata inference, prefer changing code in `utils/metadata.py`, source context in `utils/source_configs.py`, or source-specific overrides in the relevant pipeline stage instead of manually patching generated rows.

## Code style

- Use clear, small functions with explicit names.
- Keep path handling based on `pathlib.Path`.
- Keep structured records JSON/CSV-friendly: plain dictionaries, dataclasses from `utils/models.py`, strings, numbers, booleans, and lists.
- Preserve deterministic output ordering where possible; generated manifests and indices should be stable across equivalent runs.
- When adding source-specific logic, isolate it clearly and name it after the affected family/source.
- Avoid broad rewrites of the whole pipeline when a focused source-specific rule is enough.
- Avoid hidden global state beyond explicit source definitions and constants.

## Tests and validation

Before proposing or committing changes, run:

```bash
python3 -m pytest -q
```

For crawler/normalization changes, also run a small targeted pipeline command for the affected family, for example:

```bash
python3 run_pipeline.py --families spbao --discover-limit 20 --download-limit 20
```

For cleanup behavior, prefer tests over manual inspection. The cleanup code is intentionally destructive for generated outputs, so changes there need extra care.

## Working with committed indices/manifests

Committed indices and discovery manifests are useful public metadata snapshots. They may change when pipeline behavior changes, but avoid manual edits unless the task is explicitly a metadata correction.

OWAO combines priority-1 official discovery with the priority-2 direct-file Astroedu fallback. Direct theoretical/practical PDFs and practical data archives from `astroedu.ru/assets/problems/owao/` should be downloaded normally; robots-blocked external shares and interactive/login pages remain discovery-only. Do not add bypasses. Use the documented `data/manual/owao/` plus `import_manual_files.py` workflow only for remaining public files obtained manually.

If a change updates generated metadata, mention:

- which command produced the update;
- which families were refreshed;
- whether binary directories remained uncommitted;
- any known robots/discovery-only limitations.

## Commit guidance

Good commit boundaries:

- source configuration update for one olympiad family;
- metadata inference improvement plus tests;
- crawler behavior fix plus targeted manifest/index refresh;
- documentation-only update;
- cleanup/output-safety fix.

Avoid mixing unrelated family refreshes, large generated diffs, and refactors in one commit.

Before committing, check:

```bash
git status --short
python3 -m pytest -q
```

Make sure `data/raw/`, `data/archive/`, and `data/logs/` are absent from the commit.
