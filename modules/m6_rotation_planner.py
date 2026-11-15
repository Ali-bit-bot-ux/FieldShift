"""Agro rotation engine. Backend 2 owns this file.

Strictly implements CropRotationEngine.generate_strategies(...) against
docs/features/fieldshift/00_CONTRACT.md and dataset/rotation_rules.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

ROOT_DIR = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT_DIR / "dataset" / "rotation_rules.json"
CROPS_PATH = ROOT_DIR / "dataset" / "crops.json"
SOILS_PATH = ROOT_DIR / "dataset" / "soils.json"


class StrategyList(list):
    """List that also supports dict-like key access for 'strategies' for backward/facade compatibility."""

    def __getitem__(self, item: Any) -> Any:
        if item == "strategies":
            return self
        return super().__getitem__(item)

    def get(self, key: str, default: Any = None) -> Any:
        if key == "strategies":
            return self
        return default


class CropRotationEngine:
    """Core agronomic engine for multi-year crop rotation optimization in Kazakhstan grain belt."""

    def __init__(self) -> None:
        self.rules_data = self._load_json(RULES_PATH)
        self.crops_data = self._load_json(CROPS_PATH)
        self.soils_data = self._load_json(SOILS_PATH)

        self.crops_by_id: Dict[str, dict] = {c["id"]: c for c in self.crops_data}
        self.soils_by_id: Dict[str, dict] = {s["id"]: s for s in self.soils_data}
        self.crop_params: Dict[str, dict] = self.rules_data.get("crop_parameters", {})
        self.soil_base_health: Dict[str, int] = self.rules_data.get("initial_soil_health", {})
        self.rules_list: List[dict] = self.rules_data.get("rules", [])
        self.nitrogen_fixation: Dict[str, int] = self.rules_data.get("nitrogen_fixation_kg_ha", {
            "chickpea": 35,
            "lentil": 30,
            "pea": 25,
            "alfalfa": 45,
        })

    @staticmethod
    def _load_json(path: Path) -> Any:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # -------------------------------------------------------------------------
    # STEP 1: Agronomic Rules & Validation
    # -------------------------------------------------------------------------
    def validate_rotation_sequence(self, crops_seq: List[str]) -> Tuple[bool, List[str]]:
        """Validate sequence against rules in dataset/rotation_rules.json:
        - Max consecutive years (e.g. wheat <= 2, barley <= 2)
        - Min return interval (e.g. sunflower >= 4, flax >= 3, cotton >= 3)
        """
        violations = []
        rules_map = {r["crop_id"]: r for r in self.rules_list}

        # Check max consecutive years
        current_crop = None
        consecutive_count = 0
        for crop in crops_seq:
            if crop == current_crop:
                consecutive_count += 1
            else:
                current_crop = crop
                consecutive_count = 1

            rule = rules_map.get(crop)
            if rule and "max_consecutive_years" in rule:
                if consecutive_count > rule["max_consecutive_years"]:
                    violations.append(
                        f"Crop '{crop}' grown for {consecutive_count} consecutive years (limit {rule['max_consecutive_years']}): {rule['reason']}"
                    )

        # Check return intervals
        positions: Dict[str, List[int]] = {}
        for idx, crop in enumerate(crops_seq):
            positions.setdefault(crop, []).append(idx)

        for crop, idxs in positions.items():
            rule = rules_map.get(crop)
            if rule and "min_return_interval_years" in rule:
                min_interval = rule["min_return_interval_years"]
                for i in range(len(idxs) - 1):
                    gap = idxs[i + 1] - idxs[i]
                    if gap < min_interval:
                        violations.append(
                            f"Crop '{crop}' returned after {gap} years (minimum interval {min_interval} years): {rule['reason']}"
                        )

        return (len(violations) == 0, violations)

    # -------------------------------------------------------------------------
    # STEP 2: Soil Health Score (SHS in [0, 100])
    # Formula: SHS_t = SHS_{t-1} + Delta_legume (+12) - Delta_exhaustion (-8) + Delta_NoTill (+5)
    # Plus taproot bonus on crusting soils.
    # -------------------------------------------------------------------------
    def calculate_soil_health_step(
        self,
        prev_shs: float,
        crop_id: str,
        soil_id: str,
        is_notill: bool = True,
        is_monoculture_repeat: bool = False,
    ) -> int:
        soil_info = self.soils_by_id.get(soil_id, {})
        crop_meta = self._get_crop_meta(crop_id)

        # Base delta from crop
        delta_crop = crop_meta["soil_health_delta"]

        # No-Till bonus (preserves aggregates and stubble snow accumulation)
        delta_notill = 5 if is_notill else 0

        # Monoculture exhaustion penalty
        delta_exhaustion = -8 if is_monoculture_repeat else 0

        # Taproot bonus on crusting/compacted soils (solonetz, chestnut, sierozem)
        crust_risk = str(soil_info.get("crust_formation_risk", "")).lower()
        has_crust_risk = ("высок" in crust_risk) or ("критич" in crust_risk) or ("экстрем" in crust_risk)
        delta_taproot = 4 if (has_crust_risk and crop_meta["root_type"] == "taproot") else 0

        shs_new = prev_shs + delta_crop + delta_notill + delta_exhaustion + delta_taproot
        # Clamp strictly to [0, 100]
        return int(round(max(0.0, min(100.0, shs_new))))

    # -------------------------------------------------------------------------
    # STEP 3: Weighted Optimizer & Multi-criteria Scoring
    # Score = w1 * Yield + w2 * WaterSaving + w3 * Delta_SHS - w4 * Cost
    # Adapted with NASA climate parameters (GLDAS ET, IMERG P, SMAP Soil Moisture)
    # -------------------------------------------------------------------------
    def _normalize_priorities(self, raw_priorities: Optional[Dict[str, float]]) -> Tuple[Dict[str, float], bool]:
        """Normalize user priority weights so sum == 1.0. If all zeros or missing, set all to 0.25."""
        defaults = {
            "yield_profit": 0.25,
            "water_saving": 0.25,
            "soil_health": 0.25,
            "cost_minimization": 0.25,
        }
        if not raw_priorities:
            return defaults, True

        w_yield = max(0.0, float(raw_priorities.get("yield_profit", 0.0)))
        w_water = max(0.0, float(raw_priorities.get("water_saving", 0.0)))
        w_soil = max(0.0, float(raw_priorities.get("soil_health", 0.0)))
        w_cost = max(0.0, float(raw_priorities.get("cost_minimization", 0.0)))

        total = w_yield + w_water + w_soil + w_cost
        if total <= 1e-6:
            return defaults, True

        normalized = {
            "yield_profit": round(w_yield / total, 4),
            "water_saving": round(w_water / total, 4),
            "soil_health": round(w_soil / total, 4),
            "cost_minimization": round(w_cost / total, 4),
        }
        return normalized, False

    def _get_crop_meta(self, crop_id: str) -> dict:
        crop_raw = self.crops_by_id.get(crop_id, {})
        param = self.crop_params.get(crop_id, {})
        return {
            "id": crop_id,
            "name_ru": crop_raw.get("name_ru", crop_id),
            "name_kk": crop_raw.get("name_kk", crop_id),
            "water_demand_mm": param.get("water_demand_mm", 350),
            "water_demand_notill_mm": param.get("water_demand_notill_mm", 330),
            "nitrogen_balance_kg_ha": param.get("nitrogen_balance_kg_ha", -20),
            "soil_health_delta": param.get("soil_health_delta", 0),
            "yield_profit_score": param.get("yield_profit_score", 75),
            "cost_score": param.get("cost_score", 50),
            "drought_tolerance": param.get("drought_tolerance", 3.0),
            "is_legume": param.get("is_legume", False),
            "root_type": param.get("root_type", "fibrous"),
        }

    def _calculate_water_saved_percent(
        self, strategy_demands: List[float], baseline_demands: List[float]
    ) -> float:
        """Calculate water saved relative to continuous wheat monoculture.
        Formula: max(0.0, (1 - avg(strategy) / avg(baseline)) * 100).
        """
        if not baseline_demands:
            return 0.0
        avg_strat = sum(strategy_demands) / len(strategy_demands)
        avg_base = sum(baseline_demands) / len(baseline_demands)
        if avg_base <= 0:
            return 0.0
        saved = (1.0 - (avg_strat / avg_base)) * 100.0
        return round(max(0.0, saved), 1)

    def _calculate_summary_score(
        self,
        weights: Dict[str, float],
        avg_yield: float,
        water_saved_pct: float,
        shs_delta: float,
        avg_cost: float,
        climate_stress_level: str,
        deficit_mm: float,
        smap_moisture: float,
        is_traditional: bool = False,
    ) -> float:
        """Calculate normalized multi-criteria score in [0, 100]."""
        # Yield component (0 - 100)
        yield_comp = avg_yield

        # Water saving component (0 - 100)
        water_comp = min(100.0, max(0.0, water_saved_pct * 2.5 + 20.0)) if not is_traditional else 15.0

        # Soil health component (0 - 100)
        soil_comp = min(100.0, max(0.0, 50.0 + shs_delta * 1.8))

        # Cost minimization component: inverted cost (0 - 100)
        cost_comp = max(0.0, 100.0 - avg_cost)

        raw_score = (
            weights["yield_profit"] * yield_comp
            + weights["water_saving"] * water_comp
            + weights["soil_health"] * soil_comp
            + weights["cost_minimization"] * cost_comp
        )

        # NASA Climate sensitivity adjustment
        stress_penalty = 0.0
        if climate_stress_level in ("SEVERE_DROUGHT", "MODERATE_DROUGHT") or deficit_mm > 150 or smap_moisture < 0.19:
            if is_traditional:
                # Monoculture severely penalized under drought
                stress_penalty = 14.0
            else:
                # Resilient rotation gets reliability bonus under drought
                stress_penalty = -2.5

        final_score = raw_score - stress_penalty
        return round(max(25.0, min(98.0, final_score)), 1)

    # -------------------------------------------------------------------------
    # STEP 4: Strategy Generators (Contract Compliant)
    # -------------------------------------------------------------------------
    def _build_traditional_risk_strategy(
        self,
        soil_id: str,
        years_count: int,
        weights: Dict[str, float],
        climate_stress: str,
        deficit_mm: float,
        smap_moisture: float,
        zero_weights_flag: bool,
    ) -> dict:
        base_shs = self.soil_base_health.get(soil_id, 62)
        shs_current = base_shs
        years = []
        demands = []

        wheat_meta = self._get_crop_meta("spring_wheat")
        penalties = [0, 7, 15, 23]
        nitrogen_drops = [0, 3, 6, 9]

        for i in range(years_count):
            yr = i + 1
            shs_current = max(20, base_shs - penalties[min(i, len(penalties) - 1)])
            n_balance = wheat_meta["nitrogen_balance_kg_ha"] - nitrogen_drops[min(i, len(nitrogen_drops) - 1)]
            w_demand = wheat_meta["water_demand_mm"]
            demands.append(w_demand)

            if yr == 1:
                r_ru = "Контрольный коммерческий сценарий монокультуры яровой пшеницы."
                r_kk = "Жаздық бидайдың бақылау монокультурасы коммерциялық сценарийі."
                if zero_weights_flag:
                    r_ru = "[Применены веса по умолчанию 0.25] " + r_ru
                    r_kk = "[Әдепкі тең салмақтар 0.25 қолданылды] " + r_kk
            elif yr == 2:
                r_ru = "Повторный посев пшеницы: накопление корневых гнилей и раннее иссушение верхнего горизонта."
                r_kk = "Бидайды қайталап егу: тамыр шірігінің көбеюі және үстіңгі қабаттың ерте кебуі."
            elif yr == 3:
                r_ru = "Истощение азота и резкий рост сорной нагрузки в монокультуре."
                r_kk = "Азот қорының сарқылуы және монокультурада арамшөп басудың күрт артуы."
            else:
                r_ru = "Критический риск фузариоза, потеря продуктивной влаги и падение урожайности до 40%."
                r_kk = "Фузариоздың қатерлі деңгейі, өнімді ылғалдың жоғалуы және өнімділіктің 40%-ға дейін төмендеуі."

            years.append({
                "year": yr,
                "crop_id": "spring_wheat",
                "crop_name_ru": "Пшеница яровая",
                "crop_name_kk": "Жаздық бидай",
                "water_demand_mm": w_demand,
                "soil_health_score": int(round(shs_current)),
                "nitrogen_balance_kg_ha": int(n_balance),
                "rationale_ru": r_ru,
                "rationale_kk": r_kk,
            })

        soil_health_delta_num = shs_current - base_shs
        delta_str = f"{soil_health_delta_num:+d}%"

        score = self._calculate_summary_score(
            weights=weights,
            avg_yield=wheat_meta["yield_profit_score"] - 25.0,  # Lower effective yield due to monoculture decay
            water_saved_pct=0.0,
            shs_delta=soil_health_delta_num,
            avg_cost=wheat_meta["cost_score"] + 15.0,  # Higher fungicide and herbicide costs
            climate_stress_level=climate_stress,
            deficit_mm=deficit_mm,
            smap_moisture=smap_moisture,
            is_traditional=True,
        )

        result = {
            "strategy_id": "traditional_risk",
            "title_ru": "Традиционная монокультура (высокий климатический риск)",
            "title_kk": "Дәстүрлі монокультура (жоғары климаттық қатер)",
            "summary_score": score,
            "water_saved_percent": 0.0,
            "soil_health_delta": delta_str,
            "rotation_years": years,
        }
        if zero_weights_flag:
            result["explain"] = "Приоритеты не заданы (все 0): использованы сбалансированные веса по 0.25."
        return result

    def _build_soil_resilience_strategy(
        self,
        soil_id: str,
        years_count: int,
        weights: Dict[str, float],
        climate_stress: str,
        deficit_mm: float,
        smap_moisture: float,
        baseline_demands: List[float],
        zero_weights_flag: bool,
    ) -> dict:
        base_shs = self.soil_base_health.get(soil_id, 62)
        shs_current = base_shs

        crops_seq = ["chickpea", "spring_wheat", "alfalfa"] if years_count == 3 else ["chickpea", "spring_wheat", "alfalfa", "spring_barley"]

        years = []
        demands = []
        yields = []
        costs = []

        for i, crop_id in enumerate(crops_seq):
            yr = i + 1
            meta = self._get_crop_meta(crop_id)
            w_demand = meta["water_demand_notill_mm"]
            demands.append(w_demand)
            yields.append(meta["yield_profit_score"])
            costs.append(meta["cost_score"])

            if crop_id == "chickpea":
                shs_current = self.calculate_soil_health_step(shs_current, crop_id, soil_id, is_notill=True)
                n_balance = self.nitrogen_fixation.get("chickpea", 35)
                r_ru = "Азотфиксация (+35 кг/га) и сохранение глубокой влаги перед коммерческой культурой."
                r_kk = "Азот байыту (+35 кг/га) және коммерциялық дақыл алдында терең ылғалды сақтау."
                crop_name_ru = "Нут засухоустойчивый"
                crop_name_kk = "Құрғақшылыққа төзімді нут"
                if zero_weights_flag:
                    r_ru = "[Применены веса по умолчанию 0.25] " + r_ru
                    r_kk = "[Әдепкі тең салмақтар 0.25 қолданылды] " + r_kk
            elif crop_id == "spring_wheat":
                shs_current = self.calculate_soil_health_step(shs_current, crop_id, soil_id, is_notill=True)
                n_balance = -20
                r_ru = "Коммерческий посев пшеницы по No-Till стерне после азотфиксатора без почвоутомления."
                r_kk = "Азотфиксатордан кейін топырақ шаршауынсыз No-Till сабанымен бидайдың коммерциялық егісі."
                crop_name_ru = "Пшеница яровая по No-Till"
                crop_name_kk = "No-Till жаздық бидай"
            elif crop_id == "alfalfa":
                shs_current = self.calculate_soil_health_step(shs_current, crop_id, soil_id, is_notill=True)
                n_balance = self.nitrogen_fixation.get("alfalfa", 45)
                r_ru = "Глубокая корневая система разуплотняет плужную подошву и накапливает гумус (+45 кг/га N)."
                r_kk = "Терең тамыр жүйесі соқа табанын қопысытып, гумус пен азотты жинақтайды (+45 кг/га N)."
                crop_name_ru = "Люцерна посевная"
                crop_name_kk = "Жоңышқа"
            else:  # spring_barley
                shs_current = self.calculate_soil_health_step(shs_current, crop_id, soil_id, is_notill=True)
                n_balance = -10
                r_ru = "Раннеспелый ячмень оставляет высокую стерню для снегозадержания перед новым циклом."
                r_kk = "Ерте пісетін арпа жаңа цикл алдында қар тоқтату үшін биік сабан қалдырады."
                crop_name_ru = "Ячмень яровой + No-Till стерня"
                crop_name_kk = "Жаздық арпа + No-Till сабан"

            years.append({
                "year": yr,
                "crop_id": crop_id,
                "crop_name_ru": crop_name_ru,
                "crop_name_kk": crop_name_kk,
                "water_demand_mm": w_demand,
                "soil_health_score": int(round(shs_current)),
                "nitrogen_balance_kg_ha": int(n_balance),
                "rationale_ru": r_ru,
                "rationale_kk": r_kk,
            })

        soil_health_delta_num = shs_current - base_shs
        delta_str = f"{soil_health_delta_num:+d}%"
        water_saved = self._calculate_water_saved_percent(demands, baseline_demands)

        score = self._calculate_summary_score(
            weights=weights,
            avg_yield=sum(yields) / len(yields),
            water_saved_pct=water_saved,
            shs_delta=soil_health_delta_num,
            avg_cost=sum(costs) / len(costs),
            climate_stress_level=climate_stress,
            deficit_mm=deficit_mm,
            smap_moisture=smap_moisture,
            is_traditional=False,
        )

        result = {
            "strategy_id": "soil_resilience",
            "title_ru": "Максимум восстановления почвы (Soil Saver)",
            "title_kk": "Топырақты максималды қалпына келтіру",
            "summary_score": score,
            "water_saved_percent": water_saved,
            "soil_health_delta": delta_str,
            "rotation_years": years,
        }
        if zero_weights_flag:
            result["explain"] = "Приоритеты не заданы (все 0): использованы сбалансированные веса по 0.25."
        return result

    def _build_recommended_strategy(
        self,
        soil_id: str,
        years_count: int,
        weights: Dict[str, float],
        climate_stress: str,
        deficit_mm: float,
        smap_moisture: float,
        baseline_demands: List[float],
        zero_weights_flag: bool,
    ) -> dict:
        base_shs = self.soil_base_health.get(soil_id, 65)
        shs_current = base_shs

        is_drought = climate_stress in ("SEVERE_DROUGHT", "MODERATE_DROUGHT") or deficit_mm > 140 or smap_moisture < 0.19
        soil_has_crust_risk = soil_id in ("chestnut_dark_light", "solonchak_solonetz", "sierozem_calcareous")

        if years_count == 3:
            crops_seq = ["spring_wheat", "chickpea", "spring_barley"]
        else:
            oilseed = "safflower" if (is_drought and soil_has_crust_risk) else "flax_linseed"
            crops_seq = ["spring_wheat", "chickpea", oilseed, "spring_barley"]

        years = []
        demands = []
        yields = []
        costs = []

        for i, crop_id in enumerate(crops_seq):
            yr = i + 1
            meta = self._get_crop_meta(crop_id)
            w_demand = meta["water_demand_notill_mm"] if yr > 1 else meta["water_demand_mm"]
            demands.append(w_demand)
            yields.append(meta["yield_profit_score"])
            costs.append(meta["cost_score"])

            if crop_id == "spring_wheat":
                shs_current = base_shs
                n_balance = -25
                r_ru = "Стартовая высокодоходная культура с надежным сбытом зерна."
                r_kk = "Өткізу нарығы жоғары сенімді бастапқы табысты дақыл."
                crop_name_ru = "Пшеница яровая"
                crop_name_kk = "Жаздық бидай"
                if zero_weights_flag:
                    r_ru = "[Применены веса по умолчанию 0.25] " + r_ru
                    r_kk = "[Әдепкі тең салмақтар 0.25 қолданылды] " + r_kk
            elif crop_id == "chickpea":
                shs_current = self.calculate_soil_health_step(shs_current, crop_id, soil_id, is_notill=True)
                n_balance = self.nitrogen_fixation.get("chickpea", 35)
                r_ru = "Симбиотическая азотфиксация (+35 кг/га) и разрыв цикла злаковых корневых гнилей. Экономия влаги 35%."
                r_kk = "Азотпен байыту (+35 кг/га) және астық тамыр ауруларының циклін үзу. Ылғалды 35% үнемдеу."
                crop_name_ru = "Нут засухоустойчивый"
                crop_name_kk = "Құрғақшылыққа төзімді нут"
            elif crop_id == "flax_linseed":
                shs_current = self.calculate_soil_health_step(shs_current, crop_id, soil_id, is_notill=True)
                n_balance = -10
                r_ru = "Стержневая корневая система структурирует пахотный слой почвы и разрушает подплужную подошву."
                r_kk = "Кіндік тамыр топырақ құрылымын жақсартып, соқа табанын бұзады."
                crop_name_ru = "Лен масличный"
                crop_name_kk = "Майлы зығыр"
            elif crop_id == "safflower":
                shs_current = self.calculate_soil_health_step(shs_current, crop_id, soil_id, is_notill=True)
                n_balance = -12
                r_ru = "Глубокий стержневой корень (до 2 м) извлекает остаточную влагу и разрушает солонцеватую корку при засухе."
                r_kk = "Терең кіндік тамыр (2 м-ге дейін) тереңдегі ылғалды тартып, сортаң қыртысты бұзады."
                crop_name_ru = "Сафлор красильный"
                crop_name_kk = "Мақсары"
            else:  # spring_barley
                shs_current = self.calculate_soil_health_step(shs_current, crop_id, soil_id, is_notill=True)
                n_balance = -15
                r_ru = "Короткий вегетационный период до наступления суховеев. Высокая стерня No-Till накапливает 50-70 мм талой влаги к новому циклу."
                r_kk = "Құрғақ желдер басталғанға дейінгі қысқа вегетация. No-Till биік сабаны жаңа циклге 50-70 мм ылғал жинайды."
                crop_name_ru = "Ячмень яровой + No-Till стерня"
                crop_name_kk = "Жаздық арпа + No-Till сабан"

            years.append({
                "year": yr,
                "crop_id": crop_id,
                "crop_name_ru": crop_name_ru,
                "crop_name_kk": crop_name_kk,
                "water_demand_mm": w_demand,
                "soil_health_score": int(round(shs_current)),
                "nitrogen_balance_kg_ha": int(n_balance),
                "rationale_ru": r_ru,
                "rationale_kk": r_kk,
            })

        soil_health_delta_num = shs_current - base_shs
        delta_str = f"{soil_health_delta_num:+d}%"
        water_saved = self._calculate_water_saved_percent(demands, baseline_demands)

        # Recommended rotation maximizes multi-objective balance
        score = self._calculate_summary_score(
            weights=weights,
            avg_yield=sum(yields) / len(yields) + 5.0,  # Synergy bonus from optimal rotation
            water_saved_pct=water_saved,
            shs_delta=soil_health_delta_num,
            avg_cost=sum(costs) / len(costs) - 5.0,  # Savings on nitrogen fertilizer and fungicides
            climate_stress_level=climate_stress,
            deficit_mm=deficit_mm,
            smap_moisture=smap_moisture,
            is_traditional=False,
        )

        result = {
            "strategy_id": "recommended",
            "title_ru": "Сбалансированная ротация NASA FieldShift",
            "title_kk": "NASA FieldShift теңгерімді ауыспалы егісі",
            "summary_score": score,
            "water_saved_percent": water_saved,
            "soil_health_delta": delta_str,
            "rotation_years": years,
        }
        if zero_weights_flag:
            result["explain"] = "Приоритеты не заданы (все 0): использованы сбалансированные веса по 0.25."
        return result

    def generate_strategies(
        self,
        soil_id: Union[str, Dict[str, Any]],
        region: Optional[str] = None,
        priorities: Optional[Dict[str, float]] = None,
        climate_data: Optional[Dict[str, Any]] = None,
        duration_years: int = 4,
        **kwargs: Any,
    ) -> StrategyList:
        """Generate three contrasting rotation strategies: recommended, soil_resilience, traditional_risk.
        Accepts arguments both as positional/keywords or as a single frontend payload dictionary.
        """
        # Bulletproof support: if first argument is a payload dict from facade
        if isinstance(soil_id, dict):
            payload = soil_id
            target_soil_id = str(payload.get("soil_type") or payload.get("soil_id", "chernozem_southern_ordinary"))
            target_region = str(region or payload.get("region", "sko"))
            target_priorities = priorities or payload.get("priorities")
            target_climate = climate_data or payload.get("climate_data") or payload.get("climate_context")
            target_duration = int(kwargs.get("duration_years", payload.get("duration_years", duration_years)))
        else:
            target_soil_id = str(soil_id)
            target_region = str(region or "sko")
            target_priorities = priorities
            target_climate = climate_data
            target_duration = int(kwargs.get("duration_years", duration_years))

        if target_soil_id not in self.soils_by_id:
            valid_soils = list(self.soils_by_id.keys())
            raise ValueError(f"Unknown soil_id: {target_soil_id}. Must be one of {valid_soils}")

        if target_priorities and "duration_years" in target_priorities:
            target_duration = int(target_priorities["duration_years"])

        if target_duration not in (3, 4):
            target_duration = 4 if target_duration >= 4 else 3

        weights, zero_weights_flag = self._normalize_priorities(target_priorities)

        climate_info = target_climate or {}
        climate_stress = climate_info.get("climate_stress_level", "MILD_STRESS")
        et_mm = float(climate_info.get("nasa_gldas_evapotranspiration_mm", 400.0))
        precip_mm = float(climate_info.get("nasa_imerg_precipitation_mm", 270.0))
        smap_moisture = float(climate_info.get("nasa_smap_moisture_m3m3", 0.20))
        deficit_mm = et_mm - precip_mm

        # Baseline: continuous spring wheat
        wheat_demand = self.crop_params.get("spring_wheat", {}).get("water_demand_mm", 380)
        baseline_demands = [wheat_demand] * target_duration

        traditional_strat = self._build_traditional_risk_strategy(
            soil_id=target_soil_id,
            years_count=target_duration,
            weights=weights,
            climate_stress=climate_stress,
            deficit_mm=deficit_mm,
            smap_moisture=smap_moisture,
            zero_weights_flag=zero_weights_flag,
        )

        resilience_strat = self._build_soil_resilience_strategy(
            soil_id=target_soil_id,
            years_count=target_duration,
            weights=weights,
            climate_stress=climate_stress,
            deficit_mm=deficit_mm,
            smap_moisture=smap_moisture,
            baseline_demands=baseline_demands,
            zero_weights_flag=zero_weights_flag,
        )

        recommended_strat = self._build_recommended_strategy(
            soil_id=target_soil_id,
            years_count=target_duration,
            weights=weights,
            climate_stress=climate_stress,
            deficit_mm=deficit_mm,
            smap_moisture=smap_moisture,
            baseline_demands=baseline_demands,
            zero_weights_flag=zero_weights_flag,
        )

        return StrategyList([recommended_strat, resilience_strat, traditional_strat])
