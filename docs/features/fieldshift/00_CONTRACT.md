# 00_CONTRACT.md — Спецификация контракта данных FieldShift

**Владелец контракта:** Backend 3 (Интегратор)  
**Статус:** Зафиксирован для параллельной разработки (Фронт и Бэк работают по этой схеме)

---

## 1. Входные параметры (Frontend ➔ Backend)

```json
{
  "region": "sko", // "sko" | "kostanay" | "akmola" | "pavlodar"
  "soil_type": "chernozem_southern_ordinary", // точный id из dataset/soils.json
  "field_area_ha": 400.0,
  "priorities": {
    "yield_profit": 0.35,   // Вес: 0.0 - 1.0 (Сумма = 1.0)
    "water_saving": 0.35,   // Вес: сохранение влаги по NASA SMAP/GLDAS
    "soil_health": 0.20,    // Вес: накопление гумуса и структура
    "cost_minimization": 0.10 // Вес: минимум затрат на удобрения/семена
  },
  "duration_years": 4 // 3 или 4 года
}
```

**Правила входа:**
- `soil_type` и все `crop_id` — только реальные ID из `dataset/soils.json` и `dataset/crops.json` (`spring_wheat`, `spring_barley`, `flax_linseed`, `chickpea` и т.д.).
- Веса нормализуются к сумме 1.0. Если все четыре веса равны 0 — использовать равные веса 0.25 и пометить это в `explain`.
- `field_area_ha` должен быть > 0; верхняя граница UI — 50 000 га.

---

## 2. Выходные параметры (Backend ➔ Frontend)

Функция-фасад `get_fieldshift_recommendation(payload)` возвращает список из **3 стратегий**:
1. `recommended` (Сбалансированная / Оптимум NASA)
2. `soil_resilience` (Максимальное восстановление почвы)
3. `traditional_risk` (Традиционная монокультура — для сравнения и критики)

```json
{
  "status": "success",
  "climate_context": {
    "nasa_smap_moisture_m3m3": 0.18,
    "nasa_gldas_evapotranspiration_mm": 410.0,
    "nasa_imerg_precipitation_mm": 285.0,
    "climate_stress_level": "MODERATE_DROUGHT" // NORMAL | MILD_STRESS | MODERATE_DROUGHT | SEVERE_DROUGHT
  },
  "strategies": [
    {
      "strategy_id": "recommended",
      "title_ru": "Сбалансированная ротация NASA FieldShift",
      "title_kk": "NASA FieldShift теңгерімді ауыспалы егісі",
      "summary_score": 86.4,
      "water_saved_percent": 34.0,
      "soil_health_delta": "+18%",
      "rotation_years": [
        {
          "year": 1,
          "crop_id": "spring_wheat",
          "crop_name_ru": "Пшеница яровая",
          "crop_name_kk": "Жаздық бидай",
          "water_demand_mm": 380,
          "soil_health_score": 65,
          "nitrogen_balance_kg_ha": -25,
          "rationale_ru": "Стартовая коммерческая культура с высоким сбытом.",
          "rationale_kk": "Нарықтағы жоғары сұранысқа ие бастапқы коммерциялық дақыл."
        },
        {
          "year": 2,
          "crop_id": "chickpea",
          "crop_name_ru": "Нут засухоустойчивый",
          "crop_name_kk": "Құрғақшылыққа төзімді нут",
          "water_demand_mm": 240,
          "soil_health_score": 78,
          "nitrogen_balance_kg_ha": +35,
          "rationale_ru": "Азотфиксация (+35 кг/га) и разрыв цикла злаковых болезней. Экономия влаги 35%.",
          "rationale_kk": "Азот байыту (+35 кг/га) және аурулар циклін үзу. Ылғалды 35% үнемдеу."
        },
        {
          "year": 3,
          "crop_id": "flax_linseed",
          "crop_name_ru": "Лен масличный",
          "crop_name_kk": "Майлы зығыр",
          "water_demand_mm": 290,
          "soil_health_score": 74,
          "nitrogen_balance_kg_ha": -10,
          "rationale_ru": "Глубокая структуризация пахотного горизонта стержневым корнем.",
          "rationale_kk": "Кіндік тамыр арқылы топырақтың құрылымын жақсарту."
        },
        {
          "year": 4,
          "crop_id": "spring_barley",
          "crop_name_ru": "Ячмень яровой + No-Till стерня",
          "crop_name_kk": "Жаздық арпа + No-Till сабан",
          "water_demand_mm": 280,
          "soil_health_score": 83,
          "nitrogen_balance_kg_ha": -15,
          "rationale_ru": "Снегозадержание высокой стерней (25 см), накопление 60 мм влаги к новому циклу.",
          "rationale_kk": "Биік сабанмен (25 см) қар тоқтату, жаңа циклге 60 мм ылғал жинау."
        }
      ]
    }
  ]
}
```

**Обязательно:** `strategies` содержит ровно три объекта с одинаковой схемой и `strategy_id`: `recommended`, `soil_resilience`, `traditional_risk`. Для `traditional_risk` поле `summary_score` может быть низким, но структура не меняется. Все ключи `climate_context` — ровно как в примере (`nasa_smap_moisture_m3m3`, `nasa_gldas_evapotranspiration_mm`, `nasa_imerg_precipitation_mm`, `climate_stress_level`).

