# 01_NASA_DATA.md — Техническое задание для Backend 1 (NASA Data Lead)

**Ответственный:** Backend 1  
**Зона ответственности:** Спутниковые слои NASA (GLDAS, IMERG, SMAP), модуль `pipeline/gee_client.py` и оффлайн-кэш.

---

## 🎯 Твоя задача:
Обеспечить систему реальными климатическими метриками NASA по 4 областям Казахстана (СКО, Костанай, Акмола, Павлодар).

### 1. Файлы, с которыми ты работаешь:
* ✏️ `pipeline/gee_client.py` — добавление функций извлечения NASA GLDAS и IMERG.
* ✏️ `scripts/prefetch_nasa_climate.py` — скрипт предварительного скачивания и кэширования.
* 📁 `data/processed/nasa_cache/` — папка с сохраненным parquet/JSON-кэшем.
* 🚫 **ЗАПРЕЩЕНО трогать:** `dashboard/app.py`, `modules/m6_rotation_planner.py` (чтобы не конфликтовать с другими).

---

## 📋 Чек-лист шагов:

- [ ] **Шаг 1. NASA GLDAS (Evapotranspiration & Soil Moisture):**
  - Подключить коллекцию GEE: `NASA/GLDAS/V021/NOAH/G025/T3H`.
  - Извлечь параметры: `Evap_tavg` (эвапотранспирация) и `RootMoist_inst` (влажность корневой зоны).
  - Написать функцию: `get_gldas_evapotranspiration(geometry, year)` $\to$ средний дефицит влаги (мм/сезон).
- [ ] **Шаг 2. NASA IMERG (Global Precipitation Measurement):**
  - Подключить коллекцию GEE: `NASA/GPM_L3/IMERG_V06` (или `IMERG_MONTHLY`).
  - Извлечь осадки: канал `precipitation`.
  - Написать функцию: `get_imerg_precipitation(geometry, year)` $\to$ сумма осадков (мм).
- [ ] **Шаг 3. Локальный автономный кэш (ОБЯЗАТЕЛЬНО):**
  - Запустить скрипт и сохранить готовые ряды GLDAS и IMERG за 2021–2026 гг. для 4 регионов в `data/processed/nasa_cache/`.
  - Если GEE недоступен (нет интернета на защите) — функция должна мгновенно отдавать данные из кэша.
- [ ] **Шаг 4. Прозрачный интерфейс для Интегратора:**
  - Предоставить единую функцию:
    ```python
    def get_nasa_climate_summary(region: str) -> dict:
        # возвращает ровно ключи контракта:
        # {nasa_smap_moisture_m3m3, nasa_gldas_evapotranspiration_mm,
        #  nasa_imerg_precipitation_mm, climate_stress_level}
    ```

---

## 🏁 Definition of Done (Критерий готовности):
1. `python scripts/prefetch_nasa_climate.py` выполняется без ошибок.
2. В `data/processed/nasa_cache/` лежат непустые файлы для 4 регионов.
3. При отключении интернета функция `get_nasa_climate_summary("sko")` возвращает валидный словарь из `00_CONTRACT.md`.

