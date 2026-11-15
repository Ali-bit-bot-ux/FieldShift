"""Lazy API adapter for the EcoEconomicAnalyzer RU/KK rule engine."""

from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field

from .drought_advisor import DroughtAdvisor
from .drought_dataset import DroughtDataset
from .legacy_common import LegacyRequest

router = APIRouter()


class AgroAdvisorRequest(LegacyRequest):
    crop_id: str
    soil_id: str | None = None
    growth_stage: str | None = Field(default=None, max_length=120)
    lang: Literal["ru", "kk"] = "ru"


@lru_cache(maxsize=1)
def get_engine():
    # No dataset I/O during import; failures propagate to main's 503 handler.
    return DroughtAdvisor(DroughtDataset())


def _success(data, sources, scope, lang="ru"):
    if lang == "kk":
        warnings = [
            "Бұл ережелерге негізделген білім базасы, үйретілген жасанды интеллект емес.",
            "Өнім шығынын азайту туралы сандар — деректер жиынының тұжырымдары, өлшенген немесе болжанған далалық әсер емес. Дәйексөздер ғылыми расталғандықты білдірмейді.",
            "Нақты дақыл–топырақ ережесі болмаса, жалпы үлгілер қолданылады; олардың осы алқапқа жарамдылығы тексерілмеген.",
        ]
        if scope == "generic":
            warnings.append("Нақты дақыл–топырақ ережесі жоқ: тек жалпы ұсыныстар берілді.")
    else:
        warnings = [
            "Это база знаний на правилах, а не обученный искусственный интеллект.",
            "Заявления о снижении потерь урожая — утверждения набора данных, а не измеренный или предсказанный полевой эффект. Наличие цитат не означает научную валидацию.",
            "При отсутствии точного правила культура–почва используются общие шаблоны; их применимость к конкретному полю не проверена.",
        ]
        if scope == "generic":
            warnings.append("Точное правило культура–почва отсутствует: выданы только общие рекомендации.")
    return {
        "status": "success", "module": "agroadvisor", "data": data,
        "metadata": {"kind": "knowledge_base", "sources": sorted(set(sources)),
                     "warnings": warnings, "recommendation_scope": scope},
    }


@router.post("/api/agroadvisor")
def recommend(request: AgroAdvisorRequest):
    engine = get_engine()
    dataset = engine.dataset
    for field, value, index in (
        ("crop_id", request.crop_id, dataset.crops),
        ("soil_id", request.soil_id, dataset.soils),
    ):
        if value not in index and not (field == "soil_id" and value is None):
            raise HTTPException(status_code=422, detail=[{
                "loc": ["body", field], "msg": "Unknown exact dataset ID", "type": "value_error",
            }])
    roadmap = engine.generate_roadmap(request.crop_id, request.soil_id, request.growth_stage, request.lang)
    soil_id = roadmap["soil_profile"]["id"]
    scope = "exact" if dataset.get_matrix_entry(request.crop_id, soil_id) else "generic"
    return _success(roadmap, [ref["id"] for ref in roadmap["academic_citations"]], scope, request.lang)


@router.get("/api/agroadvisor/options")
def options(lang: Literal["ru", "kk"] = "ru"):
    dataset = get_engine().dataset
    crops = []
    for crop in dataset.crops.values():
        phases = crop["critical_water_phases"]
        translated = crop.get("critical_water_phases_kk", phases)
        crops.append({
            "id": crop["id"], "name_ru": crop["name_ru"], "name_kk": crop.get("name_kk", crop["name_ru"]),
            "critical_water_phases": phases, "critical_water_phases_kk": translated,
            "stage_choices": [{"value": phase, "label_ru": phase, "label_kk": translated[i]}
                              for i, phase in enumerate(phases)],
        })
    soils = [{"id": soil["id"], "name_ru": soil["name_ru"],
              "name_kk": soil.get("name_kk", soil["name_ru"])} for soil in dataset.soils.values()]
    return _success({"crops": crops, "soils": soils}, dataset.references, "options", lang)
