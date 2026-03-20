from __future__ import annotations

from datetime import datetime

from .models import SeedRequest, SourceDefinition

CURRENT_YEAR = datetime.now().year

SOURCE_DEFINITIONS: list[SourceDefinition] = [
    SourceDefinition(
        source_id="vsosh_edsoo_official",
        label="ВсОШ астрономия: официальный раздел vserosolimp.edsoo.ru",
        olympiad_family="vsosh_astronomy",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://vserosolimp.edsoo.ru/astronom"],
        notes="Официальные требования и архивы последних лет.",
    ),
    SourceDefinition(
        source_id="vsosh_moscow_year_pages",
        label="ВсОШ астрономия: годовые страницы на vos.olimpiada.ru",
        olympiad_family="vsosh_astronomy",
        source_role="mirror",
        source_priority=2,
        strategy="vsosh_year_pages",
        notes="Глубокий архив по учебным годам, включая регион и заключительный этапы.",
        extras={"year_start": 2010, "year_end": CURRENT_YEAR},
    ),
    SourceDefinition(
        source_id="struve_moscow_year_pages",
        label="Струве: годовые страницы на vos.olimpiada.ru",
        olympiad_family="struve",
        source_role="mirror",
        source_priority=2,
        strategy="vsosh_year_pages",
        notes="Материалы олимпиады Струве на годовых страницах архива vos.olimpiada.ru.",
        extras={"year_start": 2022, "year_end": CURRENT_YEAR},
    ),
    SourceDefinition(
        source_id="owao_tasks_official",
        label="OWAO: official archive page with tasks and solutions",
        olympiad_family="owao",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://owao.siriusolymp.ru/tasks"],
        notes="Официальная страница архива OWAO с материалами прошлых лет.",
    ),
    SourceDefinition(
        source_id="serbia_astronomy_official",
        label="Serbia astronomy: official NAOK archive page",
        olympiad_family="serbia_astronomy",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://www.das.org.rs/naoc.html"],
        notes="Официальная страница NAOK / DAS с архивом задач и решений по годам.",
    ),
    SourceDefinition(
        source_id="russia_team_qual_archive",
        label="Russia team qualification: archive of qualifying tests",
        olympiad_family="russia_team_qual",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://astroedu.ru/hq/problems/"],
        notes="Архив квалификационных тестов для кандидатов в сборную России по астрономии и астрофизике.",
    ),
    SourceDefinition(
        source_id="mao_moscow_archive",
        label="МАО: архив на mos.olimpiada.ru",
        olympiad_family="mao",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://mos.olimpiada.ru/tasks/astr"],
        notes="Официальный архив задач и решений МАО.",
    ),
    SourceDefinition(
        source_id="spbao_olimpiada_archive",
        label="СПбАО: архив на olimpiada.ru",
        olympiad_family="spbao",
        source_role="archive",
        source_priority=2,
        strategy="static",
        seed_urls=["https://olimpiada.ru/activity/287/tasks"],
        notes="Архив с навигацией по годам и классам.",
    ),
    SourceDefinition(
        source_id="spbao_year_class_pages",
        label="СПбАО: годовые страницы на olimpiada.ru",
        olympiad_family="spbao",
        source_role="archive",
        source_priority=2,
        strategy="spbao_year_class_pages",
        notes="Глубокие страницы архива по годам и классам.",
        extras={"year_start": 2010, "year_end": 2023, "classes": list(range(5, 12))},
    ),
    SourceDefinition(
        source_id="ioaa_problems",
        label="IOAA: problems from past IOAA",
        olympiad_family="ioaa",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://www.ioaastrophysics.org/resources/problems-from-past-ioaa"],
        notes="Официальная подборка задач, решений и marking schemes.",
    ),
    SourceDefinition(
        source_id="ioaa_proceedings",
        label="IOAA: past proceedings",
        olympiad_family="ioaa",
        source_role="official",
        source_priority=2,
        strategy="static",
        seed_urls=["https://www.ioaastrophysics.org/resources/past-proceedings"],
        notes="Официальные proceedings с дополнительными материалами.",
    ),
    SourceDefinition(
        source_id="ioaa_past_olympiads",
        label="IOAA: past olympiads index",
        olympiad_family="ioaa",
        source_role="official",
        source_priority=2,
        strategy="static",
        seed_urls=["https://www.ioaastrophysics.org/past-olympiads"],
        notes="Официальный индекс прошлых олимпиад с годовыми страницами.",
    ),
    SourceDefinition(
        source_id="iao_eaae_index",
        label="IAO: индекс EAAE со ссылками на годы",
        olympiad_family="iao",
        source_role="archive",
        source_priority=2,
        strategy="static",
        seed_urls=["https://eaae-astronomy.org/news/international-astronomy-olympiad"],
        notes="Исторический обзор со ссылками на официальные страницы IAO.",
    ),
    SourceDefinition(
        source_id="iao_astroarena_mirror",
        label="IAO: mirror Astroarena",
        olympiad_family="iao",
        source_role="mirror",
        source_priority=2,
        strategy="static",
        seed_urls=["https://astroarena.github.io/astroarena/olympiads/iao.html"],
        notes="Подробный mirror с PDF по годам и турам.",
    ),
    SourceDefinition(
        source_id="iao_fizmat_mirror",
        label="IAO: mirror Fizmat",
        olympiad_family="iao",
        source_role="mirror",
        source_priority=3,
        strategy="static",
        seed_urls=["https://fizmat.space/international/"],
        notes="Дополнительный mirror с отдельными PDF и ZIP.",
    ),
]


def iter_seed_requests(source: SourceDefinition) -> list[SeedRequest]:
    if source.strategy == "static":
        return [
            SeedRequest(
                source_id=source.source_id,
                url=url,
                olympiad_family=source.olympiad_family,
                source_role=source.source_role,
                source_priority=source.source_priority,
            )
            for url in source.seed_urls
        ]

    if source.strategy == "vsosh_year_pages":
        seed_requests: list[SeedRequest] = []
        year_start = int(source.extras["year_start"])
        year_end = int(source.extras["year_end"])
        for end_year in range(year_start, year_end + 1):
            season_start = end_year - 1
            seed_requests.append(
                SeedRequest(
                    source_id=source.source_id,
                    url=f"https://vos.olimpiada.ru/astr/{season_start}_{end_year}",
                    olympiad_family=source.olympiad_family,
                    source_role=source.source_role,
                    source_priority=source.source_priority,
                    context={"season_start": season_start, "season_end": end_year},
                )
            )
        return seed_requests

    if source.strategy == "spbao_year_class_pages":
        seed_requests = []
        year_start = int(source.extras["year_start"])
        year_end = int(source.extras["year_end"])
        classes = list(source.extras["classes"])
        for year in range(year_start, year_end + 1):
            for grade in classes:
                seed_requests.append(
                    SeedRequest(
                        source_id=source.source_id,
                        url=f"https://olimpiada.ru/activity/287/tasks/{year}?class={grade}&year={year}",
                        olympiad_family=source.olympiad_family,
                        source_role=source.source_role,
                        source_priority=source.source_priority,
                        context={"archive_year": year, "grade": grade},
                    )
                )
        return seed_requests

    raise ValueError(f"Unsupported seed strategy: {source.strategy}")
