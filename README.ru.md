# Архив астрономических олимпиад

[English version](README.md)

`astronomy-olympiad-archive` собирает воспроизводимый локальный архив публичных материалов прошлых лет по астрономическим олимпиадам. Для публичного GitHub-репо он подготовлен как `code + metadata`, без коммита тяжёлых бинарных зеркал.

Приоритет покрытия:

1. `vsosh_astronomy`
2. `struve`
3. `owao`
4. `serbia_astronomy`
5. `russia_team_qual`
6. `spbao`
7. `mao`
8. `iao`
9. `ioaa`

## Что лежит в публичной версии

- код pipeline
- конфиг источников
- discovery-manifest и coverage-manifest
- итоговые индексы покрытия и relation groups
- документация

Тяжёлые локальные бинарные данные намеренно не коммитятся:

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
  manual/owao/          # опциональные вручную загруженные OWAO-файлы, не коммитятся
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
- `school`, `municipal`, `invitational`, `selection`
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

Полная пересборка с очисткой:

```bash
python3 run_pipeline.py --clean
```

Только очистка, без запуска pipeline:

```bash
python3 cleanup_outputs.py
```

Та же очистка через оркестратор:

```bash
python3 run_pipeline.py --clean-only
```

Только выбранные семейства:

```bash
python3 run_pipeline.py --families struve owao serbia_astronomy russia_team_qual
```

Тот же фильтр `--families` теперь применяется и к `coverage_report.md`.

Очистить и локально пересобрать только одно семейство:

```bash
python3 run_pipeline.py --clean --families spbao
```

Только очистка для выбранных семейств:

```bash
python3 cleanup_outputs.py --families spbao
```

Та же семейная очистка через оркестратор:

```bash
python3 run_pipeline.py --clean-only --families spbao
```

Замечания:

- `python3 run_pipeline.py --clean` сначала удаляет все локально сгенерированные артефакты: `data/raw/`, `data/archive/`, `data/logs/`, сгенерированные manifest-файлы и итоговые индексы.
- `python3 cleanup_outputs.py --families ...` удаляет только дерево архива выбранного семейства, соответствующие папки в `data/raw/` и общие логи. Общее объектное хранилище `data/archive/objects/` оно намеренно не трогает.
- Запуск с `--families ...` предназначен для локального точечного обновления. Чтобы снова получить полный глобальный набор manifest-файлов и индексов, после этого нужен прогон без `--families`.

## Источники первой очереди

- `vsosh_edsoo_official`: `https://vserosolimp.edsoo.ru/astronom`
- `owao_tasks_official`: страница `https://owao.siriusolymp.ru/2025en/tasks` и архивные страницы 2024 и 2023 годов
- `owao_astroedu_archive`: `https://astroedu.ru/hq/problems/owao` (direct-file fallback для теоретического и практического туров)
- `serbia_astronomy_official`: `https://www.das.org.rs/naoc.html`
- `russia_team_qual_archive`: `https://astroedu.ru/hq/problems/`
- `mao_moscow_archive`: `https://mos.olimpiada.ru/tasks/astr`
- `ioaa_problems`: `https://www.ioaastrophysics.org/resources/problems-from-past-ioaa`

Часть семейств сейчас стартует не с источника первого приоритета, а с archive/mirror-источников, прежде всего `struve`, `spbao` и `iao`.

Полный актуальный список seed-источников сохранён в [data/manifests/source_candidates.csv](data/manifests/source_candidates.csv).

## OWAO: прямой fallback Astroedu, official discovery и ручной импорт

Официальные архивные страницы OWAO остаются discovery-источником первого приоритета. Часть их файлов находится на robots-blocked, external-share, интерактивных или login-like сервисах, поэтому такие ссылки могут оставаться discovery-only.

Источник второго приоритета `owao_astroedu_archive` даёт прямые публичные PDF и ZIP с данными практического тура со страницы `https://astroedu.ru/hq/problems/owao`. Для перечисленных там лет точечный запуск

```bash
python3 run_pipeline.py --clean --families owao
```

должен скачать прямые материалы теоретического и практического туров и создать `data/archive/owao/`. Онлайн-наблюдательный и блиц-туры, ведущие в UTS, остаются discovery-only; pipeline не обходит ограничения доступа.

Ручной импорт по-прежнему нужен для публичных файлов OWAO, которых нет в прямом архиве. Положите скачанный в браузере файл в `data/manual/owao/`, добавьте обязательную sidecar-строку в `data/manual/owao/manual_manifest.jsonl`, запустите `python3 import_manual_files.py`, затем normalization/indexing.

### Как проверить OWAO локально

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

Текущий публичный snapshot по коммитимым артефактам обновлён на `2026-03-20`:

- настроенные seed-источники: `15`
- обнаруженные публичные документы: `1939`
- строки в `olympiads_index.csv`: `297`
- уникальные публичные файлы в `files_index.csv`: `1659`
- relation groups: `298`

Приоритетные семейства в текущих публичных индексах:

- `vsosh_astronomy`: `2009..2026`, 18 лет
- `struve`: `2022..2025`, 4 года
- `owao`: поддерживается official discovery за `2022..2025`
- `serbia_astronomy`: `2012..2026`, 15 лет
- `russia_team_qual`: `2016..2026`, 11 лет
- `spbao`: `2010..2024`, 15 лет
- `mao`: `2009..2025`, 10 лет
- `iao`: `1996..2023`, 27 лет
- `ioaa`: `2003..2025`, 20 лет

## Итоговые индексы

- [data/indices/coverage_report.md](data/indices/coverage_report.md)
- [data/indices/olympiads_index.csv](data/indices/olympiads_index.csv)
- [data/indices/files_index.csv](data/indices/files_index.csv)
- [data/indices/relation_groups.csv](data/indices/relation_groups.csv)

## Ограничения и известные пробелы

- Для PDF пока нет полноценного OCR/извлечения текста; near-duplicate строится по метаданным, именам и размерам файлов.
- Часть старых IAO-страниц на `issp.ac.ru` нестабильна, поэтому используются и официальные индексы, и зеркала.
- `vso.edsoo.ru` блокирует часть официальных файлов через `robots.txt`, поэтому они остаются только в discovery.
- Для OWAO поддерживаются официальные архивные страницы 2022–2025, а fallback Astroedu даёт прямые PDF теоретического/практического туров и архивы данных для перечисленных там лет. Отдельной рабочей страницы `2022en/tasks` нет (HTTP 404): official metadata за 2022 год извлекается из встроенного раздела. Онлайн-туры UTS и заблокированные внешние ссылки остаются discovery-only.
- Для `russia_team_qual` сейчас покрыт только direct-PDF-поднабор с `astroedu.ru/assets/problems/hq/...pdf`; связанные quiz-страницы на `uts.astroedu.ru` намеренно оставлены вне первого патча.
- В старых архивах СПбАО и ВсОШ есть битые ссылки (`404`), особенно в исторических зеркалах.
- Если один файл содержит и задачи, и решения, файл не режется; это отражается в metadata.

## Для GitHub

Этот репозиторий подготовлен так, чтобы на GitHub выкладывать код и лёгкие метаданные, а полный бинарный архив пересобирать локально.

Важно:

- код в этом репозитории распространяется под лицензией `MIT`, см. [LICENSE](LICENSE)
- это не означает автоматического разрешения на перераспространение скачанных олимпиадных файлов; для них нужно отдельно учитывать условия исходных источников
