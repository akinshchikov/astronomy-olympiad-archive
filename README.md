# Astronomy Olympiad Archive Pipeline

Репозиторий собирает воспроизводимый локальный архив публичных материалов прошлых лет по астрономическим олимпиадам. Для публичного GitHub-репо он подготовлен как `code + metadata`, без коммита тяжёлых бинарных зеркал.

Приоритет покрытия:

1. `vsosh_astronomy`
2. `spbao`
3. `mao`
4. `iao`
5. `ioaa`

## Что лежит в публичной версии

- код pipeline
- конфиг источников
- discovery-manifest и coverage-manifest
- итоговые индексы покрытия и relation groups
- документация

Локальные бинарные данные intentionally не коммитятся:

- `data/raw/`
- `data/archive/`
- `data/logs/`

Правила публикации собраны в [PUBLISHING.md](PUBLISHING.md).

## Pipeline

1. [discover_sources.py](discover_sources.py)
2. [crawl_source.py](crawl_source.py)
3. [normalize_archive.py](normalize_archive.py)
4. [detect_relations.py](detect_relations.py)
5. [build_indices.py](build_indices.py)

Оркестрация:

- [run_pipeline.py](run_pipeline.py)

Скрипты работают только с публичными URL, уважают `robots.txt`, пишут логи и продолжают работу при ошибках отдельных источников.

## Структура

```text
data/
  raw/                  # локальные оригинальные загрузки, не коммитятся
  archive/              # локальный нормализованный архив, не коммитится
    objects/            # локальное объектное хранилище по sha256
  manifests/
    source_candidates.csv
    discovered_documents.jsonl
    discovery_coverage.csv
    download_manifest.jsonl        # локальный, не коммитится
    normalized_entries.jsonl       # локальный, не коммитится
    relation_edges.jsonl           # локальный, не коммитится
  indices/
    olympiads_index.csv
    files_index.csv
    relation_groups.csv
    coverage_report.md
  logs/                 # локальные логи, не коммитятся
```

Нормализованное имя файла:

```text
<year|unknown-year>--<olympiad-family>--<stage-or-round>--<document-type>--<lang>--<descriptor-1>[--<descriptor-2>...]--<variant-tag>.<ext>
```

Примеры:

- `2024--vsosh-astronomy--qualifying--tasks--ru--grade-10--school--mirror.pdf`
- `2024--vsosh-astronomy--final--tasks--ru--grade-10--theory--mirror.pdf`
- `2025--ioaa--observational--tasks--en--planetarium--questions--official.pdf`
- `unknown-year--iao--theoretical--tasks--en--tasks-page--archive.html`

Вместо одного длинного `detail_tag` имя теперь собирается из отдельных смысловых частей: класс, программа/подэтап, тур, тип материала. Типичные дескрипторы:

- `grade-10`, `grade-10-11`
- `theory`, `practical`, `test`, `blitz`
- `school`, `municipal`, `invitational`, `struve`
- `reference-data`, `questions`, `exam`, `problem-sheet`, `tasks-page`

Это сделано, чтобы по имени сразу было видно класс и тур, а запасной `-v2`, `-v3` использовался только там, где действительно есть несколько осмысленных вариантов одного и того же комплекта.

В каждой папке события служебные файлы лежат в `info/`:

- `event-metadata.json`
- `event-source-urls.txt`
- `event-relations.json`

`data/archive/objects/` используется как локальное объектное хранилище по `sha256`, а событийные папки содержат hardlink/copy на эти объекты.

## Запуск

Сухой прогон:

```bash
python3 run_pipeline.py --dry-run
```

Полный прогон:

```bash
python3 run_pipeline.py
```

Только приоритетные семейства:

```bash
python3 run_pipeline.py --families vsosh_astronomy spbao mao iao ioaa
```

## Источники первой очереди

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

Полный список seed-источников сохранён в [data/manifests/source_candidates.csv](data/manifests/source_candidates.csv).

## Snapshot

Текущий snapshot построен локально на `2026-03-07`:

- discovery candidates: `1828`
- successful downloads: `1585`
- normalized archive entries: `1562`
- unique physical files by `sha256`: `1546`
- relation groups: `245`

По ролям источников:

- `mirror=626`
- `official=524`
- `archive=412`

Приоритетные семейства:

- `vsosh_astronomy`: `2010..2026`, 17 лет
- `spbao`: `2010..2023`, 14 лет
- `mao`: `2011..2025`, 8 лет
- `iao`: `1996..2023`, 27 лет
- `ioaa`: `2003..2025`, 20 лет

## Итоговые индексы

- [data/indices/coverage_report.md](data/indices/coverage_report.md)
- [data/indices/olympiads_index.csv](data/indices/olympiads_index.csv)
- [data/indices/files_index.csv](data/indices/files_index.csv)
- [data/indices/relation_groups.csv](data/indices/relation_groups.csv)

## Ограничения и known gaps

- Для PDF пока нет полноценного OCR/извлечения текста; near-duplicate строится по метаданным, именам и размерам файлов.
- Часть старых IAO-страниц на `issp.ac.ru` нестабильна, поэтому используются и официальные индексы, и зеркала.
- `vso.edsoo.ru` блокирует часть официальных файлов через `robots.txt`, поэтому они остаются только в discovery.
- В старых архивах СПбАО и ВсОШ есть битые ссылки (`404`), особенно в исторических зеркалах.
- Если один файл содержит и задачи, и решения, файл не режется; это отражается в metadata.

## Для GitHub

Этот репозиторий подготовлен так, чтобы на GitHub выкладывать код и лёгкие метаданные, а полный бинарный архив пересобирать локально.

Важно:

- код в этом репозитории распространяется под лицензией `MIT`, см. [LICENSE](LICENSE)
- это не означает автоматического разрешения на перераспространение скачанных олимпиадных файлов; для них нужно отдельно учитывать условия исходных источников
