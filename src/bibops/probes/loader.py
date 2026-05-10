"""Load probe sets from JSON files under `data/inputs/probes/`."""
from __future__ import annotations

import json
from functools import cache

from src.bibops.probes.schema import Probe, ProbeSet
from src.common.config import PROBES_DIR


@cache
def load_probes(category: str) -> list[Probe]:
    """Load probes for a given category, e.g. 'security/pii'."""
    path = PROBES_DIR / f"{category}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Probe file not found: {path}. "
            f"Available categories: {list_categories()}"
        )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return ProbeSet.model_validate(data).probes


def list_categories() -> list[str]:
    """Return list of available probe categories (e.g. 'security/pii')."""
    if not PROBES_DIR.exists():
        return []
    return sorted(
        str(p.relative_to(PROBES_DIR).with_suffix("")).replace("\\", "/")
        for p in PROBES_DIR.rglob("*.json")
    )
