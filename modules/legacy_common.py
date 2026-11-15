import json
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed" / "legacy"
Region = Literal["sko", "kostanay", "akmola", "pavlodar"]


class LegacyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class LegacyDataUnavailable(RuntimeError):
    pass


def load_table(name: str, required_columns: tuple[str, ...] = ()) -> pd.DataFrame:
    try:
        frame = pd.read_parquet(DATA_DIR / name)
    except (OSError, ValueError) as exc:
        raise LegacyDataUnavailable(f"Cannot read legacy dataset {name}") from exc
    if frame.empty or not set(required_columns).issubset(frame.columns):
        raise LegacyDataUnavailable(f"Empty or invalid legacy dataset {name}")
    return frame


def load_json(name: str) -> dict | list:
    try:
        value = json.loads((DATA_DIR / name).read_text(encoding="utf-8"), parse_constant=lambda _: None)
    except (OSError, ValueError) as exc:
        raise LegacyDataUnavailable(f"Cannot read legacy dataset {name}") from exc
    if not isinstance(value, (dict, list)):
        raise LegacyDataUnavailable(f"Invalid legacy dataset {name}")
    return value


def table_records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records", date_format="iso"))
