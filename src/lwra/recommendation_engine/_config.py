"""Configuration access for the recommendation engine.

Loads and caches the ``co2_storage`` and ``geothermal`` screening blocks from
``thresholds.yaml`` and provides the shared rounding helper. Kept separate from
the recommender logic so the screening functions stay pure and the YAML read is
performed exactly once per process (the ``lru_cache`` is deterministic for a
given file).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "CONFIG_DIR",
    "ROUNDING_DP",
    "load_thresholds",
    "co2_storage_thresholds",
    "geothermal_thresholds",
    "round_score",
]

CONFIG_DIR: Path = Path(__file__).resolve().parent.parent / "config"
ROUNDING_DP: int = 2


@lru_cache(maxsize=1)
def load_thresholds() -> dict[str, Any]:
    """Load and cache ``thresholds.yaml``.

    Returns:
        The parsed thresholds document as a nested dictionary.

    Raises:
        FileNotFoundError: If the thresholds file is missing.
        ValueError: If the file does not parse to a mapping.

    """
    path = CONFIG_DIR / "thresholds.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Configuration root must be a mapping: {path}")
    return data


def co2_storage_thresholds() -> dict[str, Any]:
    """Return the ``co2_storage`` screening block from ``thresholds.yaml``.

    Returns:
        The CO2 storage screening configuration.

    Raises:
        KeyError: If the block is absent.

    """
    thresholds = load_thresholds()
    try:
        return dict(thresholds["co2_storage"])
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError("'co2_storage' missing from thresholds.yaml") from exc


def geothermal_thresholds() -> dict[str, Any]:
    """Return the ``geothermal`` screening block from ``thresholds.yaml``.

    Returns:
        The geothermal screening configuration.

    Raises:
        KeyError: If the block is absent.

    """
    thresholds = load_thresholds()
    try:
        return dict(thresholds["geothermal"])
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError("'geothermal' missing from thresholds.yaml") from exc


def round_score(value: float) -> float:
    """Round a value to the engine's canonical precision.

    Args:
        value: The raw value.

    Returns:
        ``value`` rounded to :data:`ROUNDING_DP` decimal places.

    """
    return round(value, ROUNDING_DP)
