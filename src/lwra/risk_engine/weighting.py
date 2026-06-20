"""Risk factor normalisation and likelihood/consequence weighting.

This module holds the deterministic primitives the risk engine builds on:

* loading and caching the externalised weights/thresholds (YAML),
* normalising each raw risk factor onto a 0-100 contribution before weighting,
* resolving the per-factor likelihood/consequence split.

Every function is a pure, stateless function of its arguments. The only state
is an ``lru_cache``-d read of the on-disk YAML, which is itself deterministic
for a given file, so results are byte-for-byte reproducible -- a prerequisite
for the publication-quality, auditable methodology described in the
architecture document.

Normalisation model
--------------------
Each factor is mapped to a 0-100 risk *contribution* (higher = more risk) using
the parameters in ``thresholds.yaml: factor_normalisation``:

* a raw value at/below ``low`` maps to 0, at/above ``high`` maps to 100, linear
  in between;
* ``invert: true`` flips the mapping (used for ``integrity_score`` -- better
  integrity means lower risk -- and ``proximity_to_receptors`` -- closer means
  higher risk);
* ``fluid_hazard`` is a direct table lookup from
  ``weights.yaml: fluid_hazard_scores`` rather than a linear map;
* ``default_when_unknown`` supplies a conservative contribution when the raw
  input is missing.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from lwra.config.enums import RiskFactor

__all__ = [
    "CONFIG_DIR",
    "ROUNDING_DP",
    "load_weights",
    "load_thresholds",
    "risk_factor_weights",
    "fluid_hazard_scores",
    "likelihood_consequence_split",
    "clamp",
    "round_score",
    "normalise_linear",
    "normalise_factor",
    "weighted_axis_score",
]

# Location of the externalised configuration. The engine reads the *same* files
# documented in the config module; nothing is hard-coded in Python.
CONFIG_DIR: Path = Path(__file__).resolve().parent.parent / "config"

# All published scores are rounded to this many decimal places so that results
# are reproducible across platforms and serialisation round-trips.
ROUNDING_DP: int = 2


@lru_cache(maxsize=1)
def load_weights() -> dict[str, Any]:
    """Load and cache ``weights.yaml``.

    Returns:
        The parsed weights document as a nested dictionary.

    Raises:
        FileNotFoundError: If the weights file is missing.
        ValueError: If the file does not parse to a mapping.

    """
    return _load_yaml(CONFIG_DIR / "weights.yaml")


@lru_cache(maxsize=1)
def load_thresholds() -> dict[str, Any]:
    """Load and cache ``thresholds.yaml``.

    Returns:
        The parsed thresholds document as a nested dictionary.

    Raises:
        FileNotFoundError: If the thresholds file is missing.
        ValueError: If the file does not parse to a mapping.

    """
    return _load_yaml(CONFIG_DIR / "thresholds.yaml")


def _load_yaml(path: Path) -> dict[str, Any]:
    """Parse a YAML file and assert it is a mapping."""
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Configuration root must be a mapping: {path}")
    return data


def risk_factor_weights() -> dict[str, float]:
    """Return the risk factor weight block from ``weights.yaml``.

    Returns:
        Mapping of risk factor key -> weight. Validated to sum to 1.0 within a
        small tolerance so that the aggregate stays on a true 0-100 scale.

    Raises:
        KeyError: If the block is absent.
        ValueError: If the weights do not sum to 1.0 within tolerance.

    """
    weights = load_weights()
    try:
        block = {str(k): float(v) for k, v in weights["risk_factor_weights"].items()}
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError("'risk_factor_weights' missing from weights.yaml") from exc
    total = sum(block.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"risk_factor_weights must sum to 1.0 (got {total:.6f}).")
    return block


def fluid_hazard_scores() -> dict[str, float]:
    """Return the fluid hazard score table from ``weights.yaml``.

    Returns:
        Mapping of :class:`~lwra.models.enums.FluidType` value -> hazard score
        (0-100).

    Raises:
        KeyError: If the block is absent.

    """
    weights = load_weights()
    try:
        block = weights["fluid_hazard_scores"]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError("'fluid_hazard_scores' missing from weights.yaml") from exc
    return {str(k): float(v) for k, v in block.items()}


def likelihood_consequence_split() -> dict[str, dict[str, float]]:
    """Return the per-factor likelihood/consequence split from ``weights.yaml``.

    Returns:
        Mapping of factor key -> ``{"likelihood": w_l, "consequence": w_c}``
        where the two shares sum to 1.0 for each factor.

    Raises:
        KeyError: If the block is absent.

    """
    weights = load_weights()
    try:
        block = weights["likelihood_consequence"]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError("'likelihood_consequence' missing from weights.yaml") from exc
    return {
        str(k): {"likelihood": float(v["likelihood"]), "consequence": float(v["consequence"])}
        for k, v in block.items()
    }


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp ``value`` into the inclusive ``[low, high]`` range.

    Args:
        value: The value to clamp.
        low: Inclusive lower bound.
        high: Inclusive upper bound.

    Returns:
        ``value`` constrained to ``[low, high]``.

    """
    return max(low, min(high, value))


def round_score(value: float) -> float:
    """Round a score to the engine's canonical precision.

    Args:
        value: The raw score.

    Returns:
        ``value`` rounded to :data:`ROUNDING_DP` decimal places.

    """
    return round(value, ROUNDING_DP)


def normalise_linear(
    value: float,
    low: float,
    high: float,
    *,
    invert: bool = False,
) -> float:
    """Map a raw value onto a 0-100 risk contribution via a linear ramp.

    Values at/below ``low`` map to 0 and at/above ``high`` map to 100 (or the
    reverse when ``invert`` is set). The mapping is intentionally linear so the
    relationship between an input and its risk contribution is transparent.

    Args:
        value: The raw factor value.
        low: Lower anchor of the ramp.
        high: Upper anchor of the ramp.
        invert: When ``True``, a low raw value yields a high contribution.

    Returns:
        A risk contribution in [0, 100].

    Raises:
        ValueError: If ``high == low`` (degenerate ramp).

    """
    if high == low:
        raise ValueError("normalise_linear requires high != low.")
    fraction = (value - low) / (high - low)
    fraction = max(0.0, min(1.0, fraction))
    if invert:
        fraction = 1.0 - fraction
    return clamp(fraction * 100.0)


def normalise_factor(
    factor: RiskFactor,
    raw_value: float | None,
    *,
    fluid_key: str | None = None,
) -> tuple[float, dict[str, Any]]:
    """Normalise a single risk factor to a 0-100 contribution with a trace.

    Dispatches on the factor's normalisation parameters in
    ``thresholds.yaml: factor_normalisation``:

    * ``fluid_hazard`` -> table lookup keyed by ``fluid_key``;
    * factors with a ``source`` other than fluid -> not supported here;
    * everything else -> linear ramp with optional ``invert``.

    When ``raw_value`` is ``None`` and the factor defines
    ``default_when_unknown``, that conservative default contribution is used and
    recorded in the trace.

    Args:
        factor: The risk factor to normalise.
        raw_value: The raw input value, or ``None`` if unavailable. Ignored for
            ``fluid_hazard`` (which uses ``fluid_key``).
        fluid_key: The :class:`~lwra.models.enums.FluidType` value, required for
            the ``fluid_hazard`` factor.

    Returns:
        ``(contribution, trace)`` where ``contribution`` is in [0, 100] and
        ``trace`` records the inputs, parameters, and method used.

    Raises:
        KeyError: If the factor has no normalisation parameters.
        ValueError: If ``fluid_hazard`` is requested without a ``fluid_key``.

    """
    params_all = load_thresholds()["factor_normalisation"]
    key = factor.value
    if key not in params_all:
        raise KeyError(f"No normalisation parameters for factor '{key}'.")
    params = params_all[key]

    # Fluid hazard: direct table lookup, never a linear ramp.
    if params.get("source") == "fluid_hazard_scores":
        if fluid_key is None:
            raise ValueError("fluid_hazard normalisation requires a fluid_key.")
        table = fluid_hazard_scores()
        # Fall back to the configured 'unknown' default if the key is missing.
        contribution = float(table.get(fluid_key, table.get("unknown", 0.0)))
        contribution = clamp(contribution)
        return round_score(contribution), {
            "factor": key,
            "method": "fluid_hazard_scores table lookup",
            "fluid": fluid_key,
            "looked_up_in_table": fluid_key in table,
            "raw_contribution": round_score(contribution),
            "contribution": round_score(contribution),
        }

    # Missing value: use the configured conservative default if present.
    if raw_value is None:
        default = params.get("default_when_unknown")
        if default is None:
            # No default defined -> treat as zero contribution but record it.
            return 0.0, {
                "factor": key,
                "method": "missing value, no default_when_unknown -> 0.0",
                "raw_value": None,
                "contribution": 0.0,
            }
        contribution = clamp(float(default))
        return round_score(contribution), {
            "factor": key,
            "method": "missing value -> default_when_unknown",
            "raw_value": None,
            "default_when_unknown": round_score(contribution),
            "contribution": round_score(contribution),
        }

    invert = bool(params.get("invert", False))
    low = float(params["low"])
    high = float(params["high"])
    contribution = normalise_linear(float(raw_value), low, high, invert=invert)
    return round_score(contribution), {
        "factor": key,
        "method": "linear ramp" + (" (inverted)" if invert else ""),
        "raw_value": raw_value,
        "low": low,
        "high": high,
        "invert": invert,
        "contribution": round_score(contribution),
    }


def weighted_axis_score(
    contributions: dict[str, float],
    weights: dict[str, float],
    split: dict[str, dict[str, float]],
    axis: str,
) -> tuple[float, dict[str, dict[str, float]]]:
    """Compute one risk-matrix axis (likelihood or consequence).

    Each factor's normalised contribution is weighted by its overall risk
    weight *and* by its share of the requested ``axis``, then renormalised by
    the total axis weight so the axis stays on a true 0-100 scale even though
    factors split their weight across both axes.

    Args:
        contributions: Factor key -> 0-100 normalised contribution.
        weights: Factor key -> overall risk weight (sums to 1.0).
        split: Factor key -> ``{"likelihood": .., "consequence": ..}`` shares.
        axis: Either ``"likelihood"`` or ``"consequence"``.

    Returns:
        ``(axis_score, per_factor)`` where ``axis_score`` is in [0, 100] and
        ``per_factor`` records each factor's effective axis weight and
        weighted contribution.

    Raises:
        ValueError: If ``axis`` is not a recognised axis name.

    """
    if axis not in ("likelihood", "consequence"):
        raise ValueError(f"Unknown axis '{axis}'.")

    per_factor: dict[str, dict[str, float]] = {}
    weighted_sum = 0.0
    axis_weight_total = 0.0
    for key, contribution in contributions.items():
        overall_weight = weights[key]
        axis_share = split[key][axis]
        effective_weight = overall_weight * axis_share
        axis_weight_total += effective_weight
        weighted_contribution = contribution * effective_weight
        weighted_sum += weighted_contribution
        per_factor[key] = {
            "contribution": round_score(contribution),
            "overall_weight": overall_weight,
            "axis_share": axis_share,
            "effective_weight": round_score(effective_weight),
            "weighted_contribution": round_score(weighted_contribution),
        }

    axis_score = clamp(weighted_sum / axis_weight_total) if axis_weight_total > 0 else 0.0
    return round_score(axis_score), per_factor
