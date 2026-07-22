# Astronomy Olympiad Archive

[Русская версия](README.ru.md)

`astronomy-olympiad-archive` is a reproducible local archive builder for publicly available materials from past astronomy olympiads. The public GitHub repository is intentionally prepared as `code + metadata`, without committing mirrored binary files.

Priority coverage:

1. `vsosh_astronomy`
2. `struve`
3. `owao`
4. `serbia_astronomy`
5. `russia_team_qual`
6. `spbao`
7. `mao`
8. `iao`
9. `ioaa`

## What the public repository contains

- pipeline code
- source configuration
- discovery and coverage manifests
- coverage indices and relation-group summaries
- documentation

Large local binary data is intentionally not committed:

- `data/raw/`
- `data/archive/`
- `data/logs/`

Publishing notes are collected in [PUBLISHING.md](PUBLISHING.md).

## Pipeline

1. [discover_sources.py](discover_sources.py)
2. [crawl_source.py](crawl_source.py)
3. [normalize_archive.py](normalize_archive.py)
4. [detect_relations.py](detect_relations.py)
5. [build_indices.py](build_indices.py)

Orchestration:

- [run_pipeline.py](run_pipeline.py)

The scripts use only public URLs, respect `robots.txt`, write logs, and continue running when individual sources fail.

## Structure

```text
data/
  raw/                  # local original downloads, not committed
  archive/              # local normalized archive, not committed
    objects/            # local object store by sha256
  manifests/
    source_candidates.csv
    discovered_documents.jsonl
    discovery_coverage.csv
    download_manifest.jsonl        # local, not committed
    normalized_entries.jsonl       # local, not committed
    relation_edges.jsonl           # local, not committed
  indices/
    olympiads_index.csv
    files_index.csv
    relation_groups.csv
    coverage_report.md
  logs/                 # local logs, not committed
  manual/owao/          # optional manually downloaded OWAO files, not committed
```

Normalized filename format:

```text
<year|unknown-year>--<olympiad-family>--<stage-or-round>--<document-type>--<lang>--<descriptor-1>[--<descriptor-2>...]--<variant-tag>.<ext>
```

Examples:

- `2024--vsosh-astronomy--qualifying--tasks--ru--grade-10--school--mirror.pdf`
- `2024--vsosh-astronomy--final--tasks--ru--grade-10--theory--mirror.pdf`
- `2025--ioaa--observational--tasks--en--planetarium--questions--official.pdf`
- `unknown-year--iao--theoretical--tasks--en--tasks-page--archive.html`

Instead of one long `detail_tag`, the filename is now built from separate meaningful parts: grade, sub-track, round, and material type. Typical descriptors:

- `grade-10`, `grade-10-11`
- `theory`, `practical`, `test`, `blitz`
- `school`, `municipal`, `invitational`, `selection`
- `reference-data`, `questions`, `exam`, `problem-sheet`, `tasks-page`

This is meant to make the grade and round visible directly in the filename, while the fallback suffix `-v2`, `-v3`, and so on is used only when there are genuinely multiple meaningful variants of the same package.

Each event folder stores service files in `info/`:

- `event-metadata.json`
- `event-source-urls.txt`
- `event-relations.json`

`data/archive/objects/` is a local object store keyed by `sha256`, while event folders contain hardlinks or copies pointing to those objects.

## Running

Dry run:

```bash
python3 run_pipeline.py --dry-run
```

Full run:

```bash
python3 run_pipeline.py
```

Full clean rebuild:

```bash
python3 run_pipeline.py --clean
```

Cleanup only, without running the pipeline:

```bash
python3 cleanup_outputs.py
```

The same cleanup via the orchestrator:

```bash
python3 run_pipeline.py --clean-only
```

Selected families only:

```bash
python3 run_pipeline.py --families struve owao serbia_astronomy russia_team_qual
```

The same `--families` filter now also applies to `coverage_report.md`.

Clean and rebuild only one family locally:

```bash
python3 run_pipeline.py --clean --families spbao
```

Cleanup only for selected families:

```bash
python3 cleanup_outputs.py --families spbao
```

The same family cleanup via the orchestrator:

```bash
python3 run_pipeline.py --clean-only --families spbao
```

Notes:

- `python3 run_pipeline.py --clean` removes all generated local outputs first: `data/raw/`, `data/archive/`, `data/logs/`, generated manifests, and generated indices.
- `python3 cleanup_outputs.py --families ...` removes only the selected family archive tree, matching raw source folders, and shared logs. It intentionally does not delete the shared `data/archive/objects/` store.
- A focused run with `--families ...` is meant for local targeted refreshes. To rebuild the complete global manifests and indices again, run the pipeline without `--families`.

## First-priority source seeds

- `vsosh_edsoo_official`: `https://vserosolimp.edsoo.ru/astronom`
- `owao_tasks_official`: `https://owao.siriusolymp.ru/2025en/tasks`, plus the 2024 and 2023 archive pages
- `owao_astroedu_archive`: `https://astroedu.ru/hq/problems/owao` (direct-file fallback for theoretical/practical materials)
- `serbia_astronomy_official`: `https://www.das.org.rs/naoc.html`
- `russia_team_qual_archive`: `https://astroedu.ru/hq/problems/`
- `mao_moscow_archive`: `https://mos.olimpiada.ru/tasks/astr`
- `ioaa_problems`: `https://www.ioaastrophysics.org/resources/problems-from-past-ioaa`

Some families currently start from archive/mirror seeds rather than a priority-1 official source, notably `struve`, `spbao`, and `iao`.

The full current seed-source list is stored in [data/manifests/source_candidates.csv](data/manifests/source_candidates.csv).

## OWAO: direct Astroedu fallback, official discovery, and manual import

The official OWAO archive pages remain the priority-1 discovery source. Some of their files are hosted on robots-blocked, external-share, interactive, or login-like services, so those links may remain discovery-only.

The priority-2 `owao_astroedu_archive` source provides direct public PDFs and practical-round ZIP data from `https://astroedu.ru/hq/problems/owao`. For the years currently listed there, a focused run

```bash
python3 run_pipeline.py --clean --families owao
```

should download the direct theoretical and practical materials and create `data/archive/owao/`. Online observation/blitz rounds linked to UTS remain discovery-only; the pipeline does not bypass access restrictions.

Manual import remains available for public OWAO files not covered by the direct archive. Place a browser-downloaded file under `data/manual/owao/`, add the required sidecar row to `data/manual/owao/manual_manifest.jsonl`, run `python3 import_manual_files.py`, and then run normalization/indexing.

### How to check OWAO locally

```bash
grep '^owao' data/manifests/discovery_coverage.csv
python3 - <<'PY'
import json
from collections import Counter

rows = []
with open("data/manifests/discovered_documents.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("olympiad_family") == "owao":
            rows.append(r)

print("OWAO discovered rows:", len(rows))
for k, v in sorted(Counter((r.get("year"), r.get("stage_or_round"), r.get("document_type")) for r in rows).items()):
    print(v, k)
PY
find data/archive -maxdepth 3 -type d -name 'owao' -print
```

## Snapshot

Current tracked public snapshot refreshed on `2026-03-20`:

- configured seed sources: `15`
- discovered public documents: `1939`
- olympiad index rows: `297`
- unique public files in `files_index.csv`: `1659`
- relation groups: `298`

Priority families in the current public indices:

- `vsosh_astronomy`: `2009..2026`, 18 years
- `struve`: `2022..2025`, 4 years
- `owao`: official discovery support for `2022..2025`
- `serbia_astronomy`: `2012..2026`, 15 years
- `russia_team_qual`: `2016..2026`, 11 years
- `spbao`: `2010..2024`, 15 years
- `mao`: `2009..2025`, 10 years
- `iao`: `1996..2023`, 27 years
- `ioaa`: `2003..2025`, 20 years

## Output indices

- [data/indices/coverage_report.md](data/indices/coverage_report.md)
- [data/indices/olympiads_index.csv](data/indices/olympiads_index.csv)
- [data/indices/files_index.csv](data/indices/files_index.csv)
- [data/indices/relation_groups.csv](data/indices/relation_groups.csv)

## Limitations and known gaps

- PDF OCR and text extraction are still limited; near-duplicate detection currently relies on metadata, filenames, and file sizes.
- Some older IAO pages on `issp.ac.ru` are unstable, so both official indexes and mirrors are used.
- `vso.edsoo.ru` blocks part of the official material through `robots.txt`, so those files remain discovery-only.
- OWAO official archive pages for 2022–2025 are discovered, while the Astroedu fallback supplies direct theoretical/practical PDFs and practical data archives for the years it lists. There is no working standalone `2022en/tasks` page (HTTP 404); official 2022 metadata is discovered from the embedded 2022 section. Online UTS rounds and blocked external shares remain discovery-only.
- `russia_team_qual` currently covers the direct-PDF subset from `astroedu.ru/assets/problems/hq/...pdf`; linked `uts.astroedu.ru` quiz pages are intentionally out of scope for now.
- Old SPbAO and VsOSh archives still contain broken historical links (`404`), especially in mirrors.
- If a single file contains both tasks and solutions, the file is not split; this is reflected in metadata.

## For GitHub

This repository is prepared for GitHub as code plus lightweight metadata, while the full binary archive is meant to be rebuilt locally.

Important:

- the code in this repository is released under `MIT`; see [LICENSE](LICENSE)
- this does not automatically grant permission to republish downloaded olympiad files; redistribution terms still depend on the original sources
