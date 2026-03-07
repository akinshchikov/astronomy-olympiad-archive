# Astronomy Olympiad Archive

[Русская версия](README.ru.md)

`astronomy-olympiad-archive` is a reproducible local archive builder for publicly available materials from past astronomy olympiads. The public GitHub repository is intentionally prepared as `code + metadata`, without committing mirrored binary files.

Priority coverage:

1. `vsosh_astronomy`
2. `spbao`
3. `mao`
4. `iao`
5. `ioaa`

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
- `school`, `municipal`, `invitational`, `struve`
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

Priority families only:

```bash
python3 run_pipeline.py --families vsosh_astronomy spbao mao iao ioaa
```

## First-priority source seeds

- `vsosh_edsoo_official`: `https://vserosolimp.edsoo.ru/astronom`
- `vsosh_moscow_year_pages`: `https://vos.olimpiada.ru/astr/<season>`
- `mao_moscow_archive`: `https://mos.olimpiada.ru/tasks/astr`
- `spbao_olimpiada_archive`: `https://olimpiada.ru/activity/287/tasks`
- `spbao_year_class_pages`: `https://olimpiada.ru/activity/287/tasks/<year>?class=<grade>&year=<year>`
- `ioaa_problems`: `https://www.ioaastrophysics.org/resources/problems-from-past-ioaa`
- `ioaa_proceedings`: `https://www.ioaastrophysics.org/resources/past-proceedings`
- `ioaa_past_olympiads`: `https://www.ioaastrophysics.org/past-olympiads`
- `iao_eaae_index`: `https://eaae-astronomy.org/news/international-astronomy-olympiad`
- `iao_astroarena_mirror`: `https://astroarena.github.io/astroarena/olympiads/iao.html`
- `iao_fizmat_mirror`: `https://fizmat.space/international/`

The full seed-source list is stored in [data/manifests/source_candidates.csv](data/manifests/source_candidates.csv).

## Snapshot

Current local snapshot built on `2026-03-07`:

- discovery candidates: `1828`
- successful downloads: `1585`
- normalized archive entries: `1562`
- unique physical files by `sha256`: `1546`
- relation groups: `245`

By source role:

- `mirror=626`
- `official=524`
- `archive=412`

Priority families:

- `vsosh_astronomy`: `2010..2026`, 17 years
- `spbao`: `2010..2023`, 14 years
- `mao`: `2011..2025`, 8 years
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
- Old SPbAO and VsOSh archives still contain broken historical links (`404`), especially in mirrors.
- If a single file contains both tasks and solutions, the file is not split; this is reflected in metadata.

## For GitHub

This repository is prepared for GitHub as code plus lightweight metadata, while the full binary archive is meant to be rebuilt locally.

Important:

- the code in this repository is released under `MIT`; see [LICENSE](LICENSE)
- this does not automatically grant permission to republish downloaded olympiad files; redistribution terms still depend on the original sources
