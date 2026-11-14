"""Integration facade. Backend 3 owns this file.
"""
import json
from pathlib import Path

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "docs/features/fieldshift/fixtures/contract_response.json"


def get_fieldshift_recommendation(payload: dict) -> dict:
    """Return the contract fixture until NASA data and rotation engine are wired."""
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
