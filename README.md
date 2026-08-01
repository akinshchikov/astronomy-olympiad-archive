# Astronomy Olympiad Archive

[Русская версия](README.ru.md)

`astronomy-olympiad-archive` is a reproducible local archive builder for publicly available materials from past astronomy olympiads. The public GitHub repository is intentionally prepared as `code + metadata`, without committing mirrored binary files.

Core baseline families:

1. `vsosh_astronomy`
2. `struve`
3. `owao`
4. `serbia_astronomy`
5. `russia_team_qual`
6. `spbao`
7. `mao`
8. `iao`
9. `ioaa`
10. `ioaa_junior`
11. `usaaao`
12. `inao`
13. `czech_astronomy`
14. `gecaa`

The archive distinguishes three coverage states. The current public indices contain
local-file metadata for 27 families; the olympiad-level index represents 32 families,
including discovery-only provenance. The [Batch C activation audit](data/audits/global_expansion_batch_c.csv)
is the authoritative record for evaluated sources that remain discovery-only,
unresolved, or deferred. A source record is not a claim that its binaries were
downloaded or that its historic archive is complete.

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

The scripts use only public URLs, respect `robots.txt`, write logs, validate the
actual response type before accepting a download, and continue when an individual
source fails. Resumable checkpoints reuse a validated local binary but refresh its
metadata from current discovery.

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
    download_checkpoint.jsonl      # local resumable-download state, not committed
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
- Focused cleanup also removes rows for the selected families from generated JSONL manifests, preventing stale records from being reused in a focused rebuild. It does not delete `data/archive/objects/`.
- Download checkpoints reuse only a validated local binary; current discovery metadata remains authoritative when a crawl is resumed.
- A focused run with `--families ...` is meant for local targeted refreshes. To rebuild the complete global manifests and indices again, run the pipeline without `--families`.

## First-priority source seeds

- `vsosh_edsoo_official`: `https://vserosolimp.edsoo.ru/astronom`
- `owao_tasks_official`: `https://owao.siriusolymp.ru/2025en/tasks`, plus the 2024 and 2023 archive pages
- `owao_astroedu_archive`: `https://astroedu.ru/hq/problems/owao` (direct-file fallback for theoretical/practical materials)
- `serbia_astronomy_official`: `https://www.das.org.rs/naoc.html`
- `russia_team_qual_archive`: `https://astroedu.ru/hq/problems/`
- `struve_astroedu_archive`: `https://astroedu.ru/struve/problems` (official; the older Moscow year pages remain a mirror)
- `mao_official_archive`: `https://mosastro.olimpiada.ru/tasks` (official; `mao_moscow_archive` remains a historical fallback)
- `ioaa_problems`: `https://www.ioaastrophysics.org/resources/problems-from-past-ioaa`

Source-policy boundaries:

- `ioaa_junior_official` keeps Junior IOAA separate from core IOAA. Its official past-olympiads PDFs can combine several competition components in one document.
- `usaaao_past_exams` preserves the competition context in its metadata, including practice, First Round, NAC, and selection exams.
- `inao_hbcse_past_papers` and `inao_hbcse_current` provide public metadata, but HBCSE’s explicit no-redistribution policy is retained as `redistribution_status=explicit-no-redistribution`. Downloaded INAO papers and solutions remain local and are not committed or republished.
- `czech_astronomy_official` is a separate Czech Astronomical Olympiad family, not IAO. Protected or unavailable material is a discovery gap; the pipeline does not bypass login or access controls and filters unrelated IAO, press, and results material.
- `gecaa_ioaa_archive` supplies available official GeCAA material from the IOAA-hosted archive. `gecaa_official_archive` remains an external availability gap: current `gecaa.ee` downloads, including known team documents, are not claimed as locally archived.

Some families currently start from archive/mirror seeds rather than a priority-1 official source, notably `spbao` and parts of `iao`. IAO targets on `issp.ac.ru` retain official target provenance even when discovered through an archive index.

Batch C keeps distinct competition lineages separate: Poland senior (`poland_astronomy`) is not Poland junior; Sri Lanka senior and junior are separate; and Slovenia high-school, primary-school, and Utrinek are three families. Bangladesh BAO is separate from BDOAA, and Macao local preliminary papers are not CNAO papers. CNAO excludes provincial Chinese feeder competitions. Nepal currently contributes only unknown-year sample/practice papers, not verified historic national rounds.

Source roles are preserved. Iran is represented by a mirror source, not an official archive; an Israel Space Agency event page does not make the Multi-Space archive authoritative. Croatia uses bounded local extraction of validated public ZIP containers; extracted members remain local. OBA retains level/category semantics and excludes unsupported training/selection material.

The full current seed-source list is stored in [data/manifests/source_candidates.csv](data/manifests/source_candidates.csv).

Interactive UTS/Edu Sirius rounds are retained as discovery-only metadata and are never authenticated or downloaded. Historical SPbAO 2012–2013 links can remain broken/undownloaded; the documented manual-import route is the supported rescue path rather than unverified mirrors.

Discovery-only Batch C coverage is intentional where policy or source access prevents safe ingestion: OLAA and NZOAA official Drive-linked files are blocked by crawler policy; Thailand files are form-gated; Singapore and Malaysia official pages are robots-blocked; and some official pages expose provenance but no safely enumerable paper archive. The audit also records unresolved and deferred candidates without placing them in runtime ingestion configuration.

## Manual source-expansion refresh

Run the full, networked metadata refresh in a persistent terminal session:

```bash
tmux new -s olympiad-refresh
./scripts/refresh_source_expansion.sh
```

Detach with `Ctrl-b d`, then resume with `tmux attach -t olympiad-refresh`. The script uses a temporary staging copy, validates the discovery snapshot before copying it back, and leaves that copy available if validation fails.

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

## Metadata semantics

- A physical document can logically represent several document types (for example, tasks and solutions). It is not split merely to force one `document_type` per file.
- `access_mode=discovery_only` retains useful public provenance that is not a download target.
- Chronology configuration distinguishes actual competition gaps from retained prehistory/anomalous years and known not-held components.

## Snapshot

Current tracked public snapshot refreshed on `2026-08-01`:

- configured seed sources: `53`
- discovered public documents: `3768`
- olympiad index rows: `687`
- unique public files in `files_index.csv`: `3538`
- relation groups: `592`

Batch C adds 940 indexed files across 13 further families: Bangladesh BAO, Brazil OBA, Bulgaria, CAAO, Croatia, Macao, Nepal, Poland senior astronomy, three distinct Slovenia lineages, and Sri Lanka senior and junior. The durable [Batch C audit](data/audits/global_expansion_batch_c.csv) has 32 candidates: 13 `INGESTED_PARTIAL`, 11 `ACTIVE_DISCOVERY_ONLY`, 7 `CONDITIONAL_UNRESOLVED`, and 1 `DEFERRED_NO_RELIABLE_ARCHIVE`.

Families with indexed local files (27; recorded-year ranges for the core baseline are below; see the coverage report for document types, discovery-only records, prehistory, and not-held components):

- `vsosh_astronomy`: `1994..2026`, 33 years
- `struve`: `2022..2026`, 5 years
- `owao`: `2022..2025`, 4 years
- `serbia_astronomy`: `2012..2026`, 15 years
- `russia_team_qual`: `2016..2026`, 11 years
- `spbao`: `2010..2026`, 17 years
- `mao`: `2010..2026`, 16 years
- `iao`: `1989..2023`, 28 years (including retained 1989 prehistory)
- `ioaa`: `2003..2025`, 20 years (2003 and 2005 retained as prehistory)
- `ioaa_junior`: `2022..2025`, 4 years
- `usaaao`: `2014..2026`, 13 years
- `inao`: `2008..2026`, 18 years
- `czech_astronomy`: `2004..2025`, 22 years
- `gecaa`: `2020`, 1 year

- Batch C: `bangladesh_bao`, `brazil_oba`, `bulgaria_astronomy`, `caao`, `croatia_astronomy`, `macao_astronomy`, `nepal_astronomy`, `poland_astronomy`, `slovenia_astronomy`, `slovenia_astronomy_primary`, `slovenia_utrinek`, `sri_lanka_astronomy`, and `sri_lanka_junior_astronomy`.

Five further olympiad-index families have provenance coverage without indexed local files: `baao`, `olaa`, `poland_astronomy_junior`, `singapore_astronomy`, and `thailand_astronomy`. Other audit candidates are deliberately unresolved or deferred rather than represented as ingested archives.

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
- INAO/HBCSE papers and solutions remain local under the explicit no-redistribution policy.
- Protected Czech AO material remains a discovery gap; no authentication or access-control bypass is attempted.
- The IOAA-hosted GeCAA archive is indexed, but the current `gecaa.ee` download failure remains an external gap, including known team documents.
- The Batch C audit retains further gaps rather than bypassing them: robots restrictions, external-host policies, form gates, unavailable archives, and mirror-only provenance do not authorize alternative scraping or redistribution.

## For GitHub

This repository is prepared for GitHub as code plus lightweight metadata, while the full binary archive is meant to be rebuilt locally.

Important:

- the code in this repository is released under `MIT`; see [LICENSE](LICENSE)
- this does not automatically grant permission to republish downloaded olympiad files; redistribution terms still depend on the original sources
