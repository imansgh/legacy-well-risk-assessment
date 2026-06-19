"""Recommendation engine: verdict, reuse suitability, actions, and rationale.

Synthesises a well's :class:`~lwra.models.results.IntegrityResult` and
:class:`~lwra.models.results.RiskResult` (plus its static
:class:`~lwra.models.well.WellData`) into an actionable
:class:`~lwra.models.results.RecommendationResult`:

* a top-level engineering **verdict** (reuse / remediate / monitor / abandon),
* **CO2 storage** suitability (ISO 27914-inspired screening),
* **geothermal** suitability screening,
* a de-duplicated list of **required actions**,
* a **confidence** score that decays with data uncertainty, and
* a human-readable **rationale**.

Design notes
------------
Every function here is a pure, deterministic function of its inputs and the
externalised configuration (``co2_storage`` and ``geothermal`` blocks of
``thresholds.yaml``). Nothing is mutated; a new immutable result is returned.

The screening logic is intentionally *gate-based* and fully traced rather than
a black-box score, so the reasoning is auditable for publication and so a
future machine-learning model can be trained against -- or blended with -- the
transparent rule outputs without changing this contract. Each suitability call
returns the level plus the list of gate evaluations that produced it.
"""

from __future__ import annotations

from typing import Any

from lwra.models.enums import (
    BarrierElement,
    SuitabilityLevel,
    Verdict,
)
from lwra.models.results import IntegrityResult, RecommendationResult, RiskResult
from lwra.models.well import WellData
from lwra.recommendation_engine._config import (
    co2_storage_thresholds,
    geothermal_thresholds,
    round_score,
)

__all__ = [
    "assess_recommendations",
    "assess_recommendations_traced",
    "assess_co2_storage_suitability",
    "assess_geothermal_suitability",
    "decide_verdict",
    "generate_required_actions",
    "compute_confidence",
    "caprock_barrier_condition",
]

# -----------------------------------------------------------------------------
# Verdict decision thresholds
# -----------------------------------------------------------------------------
# These govern the top-level engineering verdict. They are deliberately aligned
# with the integrity category bands (good >= 80, moderate >= 60, poor >= 40,
# failed < 40) and the risk category bands so the verdict reads consistently
# with the component results. Kept here (not in YAML) because they are the
# engine's decision policy rather than a tunable scoring parameter; lifting them
# into config is a clean future step if policy needs to vary per deployment.
_REUSE_MIN_INTEGRITY: float = 80.0
_REUSE_MAX_RISK: float = 25.0
_REMEDIATE_MIN_INTEGRITY: float = 40.0
_ABANDON_MAX_INTEGRITY: float = 40.0
_ABANDON_MIN_RISK: float = 76.0

# Confidence model. Confidence starts at a ceiling and is reduced by data
# uncertainty (the fraction of key fields missing, surfaced by the risk engine)
# and by the presence of integrity flags (each unresolved finding lowers trust
# in the recommendation).
_CONFIDENCE_CEILING: float = 0.98
_CONFIDENCE_FLOOR: float = 0.20
_UNCERTAINTY_WEIGHT: float = 0.60   # Max confidence lost to full uncertainty.
_PER_FLAG_PENALTY: float = 0.04     # Confidence lost per integrity flag.
_MAX_FLAG_PENALTY: float = 0.20     # Cap on total flag penalty.


def caprock_barrier_condition(well: WellData) -> tuple[float | None, dict[str, Any]]:
    """Estimate the raw caprock sealing condition from cement barriers.

    The caprock seal is approximated by the deepest cement barrier element,
    since that is the cement most likely to span the reservoir-to-caprock
    contact. Its raw ``condition_score`` (0-1) is compared against the CO2
    ``min_caprock_barrier_condition`` gate.

    Args:
        well: The well under assessment.

    Returns:
        ``(condition, trace)`` where ``condition`` is the representative raw
        caprock condition in [0, 1], or ``None`` if no cement barrier exists.
    """
    cement = [b for b in well.barriers if b.element is BarrierElement.CEMENT]
    if not cement:
        return None, {
            "method": "deepest cement barrier condition",
            "cement_barrier_count": 0,
            "caprock_condition": None,
            "note": "no cement barrier elements -> caprock condition unknown",
        }
    deepest = max(cement, key=lambda b: b.depth_bottom_m)
    return deepest.condition_score, {
        "method": "deepest cement barrier condition",
        "cement_barrier_count": len(cement),
        "selected_barrier_id": deepest.barrier_id,
        "selected_barrier_bottom_m": deepest.depth_bottom_m,
        "caprock_condition": deepest.condition_score,
    }


def _evaluate_gate(name: str, passed: bool, detail: dict[str, Any]) -> dict[str, Any]:
    """Build a single gate-evaluation trace fragment.

    Args:
        name: Gate identifier.
        passed: Whether the gate passed.
        detail: Supporting values (observed, threshold, etc.).

    Returns:
        A trace dict for the gate.
    """
    return {"gate": name, "passed": passed, **detail}


def assess_co2_storage_suitability(
    well: WellData,
    integrity: IntegrityResult,
    risk: RiskResult,
    *,
    has_verified_secondary: bool,
) -> tuple[SuitabilityLevel, dict[str, Any]]:
    """Screen the well for CO2 storage reuse (ISO 27914-inspired).

    Gate logic, reading ``co2_storage`` from ``thresholds.yaml``:

    * **Hard gates** (any failure -> ``UNSUITABLE``): overall integrity below
      ``min_overall_integrity``; risk above ``max_risk_score``; a required but
      absent verified secondary barrier; caprock condition below
      ``min_caprock_barrier_condition``; total depth below ``min_depth_m``; a
      reservoir fluid in ``disqualifying_fluids``.
    * **Insufficient data**: if caprock condition is unknown (no cement barrier)
      the screen returns ``INSUFFICIENT_DATA`` rather than passing or failing.
    * **Preferred gates** (all hard gates pass *and* integrity meets
      ``preferred_overall_integrity``) -> ``SUITABLE``; otherwise
      ``CONDITIONAL``.

    Args:
        well: The well under assessment.
        integrity: Integrity result for the well.
        risk: Risk result for the well.
        has_verified_secondary: Whether a verified secondary barrier exists.

    Returns:
        ``(level, trace)`` with the suitability level and full gate trace.
    """
    cfg = co2_storage_thresholds()
    caprock_condition, caprock_trace = caprock_barrier_condition(well)

    gates: list[dict[str, Any]] = []

    integrity_ok = integrity.overall_integrity_score >= cfg["min_overall_integrity"]
    gates.append(
        _evaluate_gate(
            "min_overall_integrity",
            integrity_ok,
            {
                "observed": integrity.overall_integrity_score,
                "threshold": cfg["min_overall_integrity"],
            },
        )
    )

    risk_ok = risk.risk_score <= cfg["max_risk_score"]
    gates.append(
        _evaluate_gate(
            "max_risk_score",
            risk_ok,
            {"observed": risk.risk_score, "threshold": cfg["max_risk_score"]},
        )
    )

    secondary_required = bool(cfg["require_verified_secondary_barrier"])
    secondary_ok = (not secondary_required) or has_verified_secondary
    gates.append(
        _evaluate_gate(
            "require_verified_secondary_barrier",
            secondary_ok,
            {"required": secondary_required, "has_verified_secondary": has_verified_secondary},
        )
    )

    depth_ok = well.total_depth_m >= cfg["min_depth_m"]
    gates.append(
        _evaluate_gate(
            "min_depth_m",
            depth_ok,
            {"observed": well.total_depth_m, "threshold": cfg["min_depth_m"]},
        )
    )

    disqualifying = {str(f) for f in cfg.get("disqualifying_fluids", [])}
    fluid_ok = well.reservoir_fluid.value not in disqualifying
    gates.append(
        _evaluate_gate(
            "disqualifying_fluids",
            fluid_ok,
            {"reservoir_fluid": well.reservoir_fluid.value, "disqualifying": sorted(disqualifying)},
        )
    )

    # Caprock gate: unknown condition -> insufficient data, not a pass/fail.
    caprock_known = caprock_condition is not None
    caprock_ok = caprock_known and caprock_condition >= cfg["min_caprock_barrier_condition"]
    gates.append(
        _evaluate_gate(
            "min_caprock_barrier_condition",
            caprock_ok,
            {
                "observed": caprock_condition,
                "threshold": cfg["min_caprock_barrier_condition"],
                "known": caprock_known,
            },
        )
    )

    hard_gate_names = {
        "min_overall_integrity",
        "max_risk_score",
        "require_verified_secondary_barrier",
        "min_depth_m",
        "disqualifying_fluids",
        "min_caprock_barrier_condition",
    }
    failed = [g["gate"] for g in gates if g["gate"] in hard_gate_names and not g["passed"]]

    if not caprock_known:
        level = SuitabilityLevel.INSUFFICIENT_DATA
        reason = "caprock condition unknown (no cement barrier)"
    elif failed:
        level = SuitabilityLevel.UNSUITABLE
        reason = f"failed hard gate(s): {', '.join(failed)}"
    elif integrity.overall_integrity_score >= cfg["preferred_overall_integrity"]:
        level = SuitabilityLevel.SUITABLE
        reason = "all hard gates passed and integrity meets preferred target"
    else:
        level = SuitabilityLevel.CONDITIONAL
        reason = "all hard gates passed but integrity below preferred target"

    trace = {
        "application": "co2_storage",
        "gates": gates,
        "caprock": caprock_trace,
        "failed_hard_gates": failed,
        "level": level.value,
        "reason": reason,
    }
    return level, trace


def assess_geothermal_suitability(
    well: WellData,
    integrity: IntegrityResult,
    risk: RiskResult,
    *,
    has_verified_secondary: bool,
) -> tuple[SuitabilityLevel, dict[str, Any]]:
    """Screen the well for geothermal reuse.

    Geothermal reuse tolerates lower containment stringency than CO2 storage but
    requires adequate temperature and depth for usable thermal energy. Gate
    logic reads the ``geothermal`` block from ``thresholds.yaml``:

    * **Insufficient data**: temperature unknown -> ``INSUFFICIENT_DATA`` (the
      thermal resource cannot be judged).
    * **Hard gates** (any failure -> ``UNSUITABLE``): integrity below
      ``min_overall_integrity``; risk above ``max_risk_score``; temperature
      below ``min_temperature_c``; depth below ``min_depth_m``; a required but
      absent verified secondary barrier.
    * **Preferred** (all hard gates pass *and* integrity meets
      ``preferred_overall_integrity`` *and* temperature meets
      ``preferred_temperature_c``) -> ``SUITABLE``; otherwise ``CONDITIONAL``.

    Args:
        well: The well under assessment.
        integrity: Integrity result for the well.
        risk: Risk result for the well.
        has_verified_secondary: Whether a verified secondary barrier exists.

    Returns:
        ``(level, trace)`` with the suitability level and full gate trace.
    """
    cfg = geothermal_thresholds()
    temperature = well.temperature_c
    gates: list[dict[str, Any]] = []

    temp_known = temperature is not None

    integrity_ok = integrity.overall_integrity_score >= cfg["min_overall_integrity"]
    gates.append(
        _evaluate_gate(
            "min_overall_integrity",
            integrity_ok,
            {
                "observed": integrity.overall_integrity_score,
                "threshold": cfg["min_overall_integrity"],
            },
        )
    )

    risk_ok = risk.risk_score <= cfg["max_risk_score"]
    gates.append(
        _evaluate_gate(
            "max_risk_score",
            risk_ok,
            {"observed": risk.risk_score, "threshold": cfg["max_risk_score"]},
        )
    )

    temp_ok = temp_known and temperature >= cfg["min_temperature_c"]
    gates.append(
        _evaluate_gate(
            "min_temperature_c",
            temp_ok,
            {"observed": temperature, "threshold": cfg["min_temperature_c"], "known": temp_known},
        )
    )

    depth_ok = well.total_depth_m >= cfg["min_depth_m"]
    gates.append(
        _evaluate_gate(
            "min_depth_m",
            depth_ok,
            {"observed": well.total_depth_m, "threshold": cfg["min_depth_m"]},
        )
    )

    secondary_required = bool(cfg["require_verified_secondary_barrier"])
    secondary_ok = (not secondary_required) or has_verified_secondary
    gates.append(
        _evaluate_gate(
            "require_verified_secondary_barrier",
            secondary_ok,
            {"required": secondary_required, "has_verified_secondary": has_verified_secondary},
        )
    )

    hard_gate_names = {
        "min_overall_integrity",
        "max_risk_score",
        "min_temperature_c",
        "min_depth_m",
        "require_verified_secondary_barrier",
    }
    failed = [g["gate"] for g in gates if g["gate"] in hard_gate_names and not g["passed"]]

    if not temp_known:
        level = SuitabilityLevel.INSUFFICIENT_DATA
        reason = "temperature unknown (thermal resource cannot be judged)"
    elif failed:
        level = SuitabilityLevel.UNSUITABLE
        reason = f"failed hard gate(s): {', '.join(failed)}"
    elif (
        integrity.overall_integrity_score >= cfg["preferred_overall_integrity"]
        and temperature >= cfg["preferred_temperature_c"]
    ):
        level = SuitabilityLevel.SUITABLE
        reason = "all hard gates passed; integrity and temperature meet preferred targets"
    else:
        level = SuitabilityLevel.CONDITIONAL
        reason = "all hard gates passed but integrity or temperature below preferred target"

    trace = {
        "application": "geothermal",
        "gates": gates,
        "failed_hard_gates": failed,
        "level": level.value,
        "reason": reason,
    }
    return level, trace


def decide_verdict(
    integrity: IntegrityResult,
    risk: RiskResult,
    co2: SuitabilityLevel,
    geothermal: SuitabilityLevel,
) -> tuple[Verdict, dict[str, Any]]:
    """Decide the top-level engineering verdict.

    Decision policy, evaluated in order:

    * **ABANDON** -- integrity is below ``_ABANDON_MAX_INTEGRITY`` (failed band)
      or risk is at/above ``_ABANDON_MIN_RISK`` (critical band): the well cannot
      be relied upon and no reuse pathway is open.
    * **REUSE** -- integrity at/above ``_REUSE_MIN_INTEGRITY`` and risk at/below
      ``_REUSE_MAX_RISK`` and at least one application is ``SUITABLE``: the well
      is in good condition with a clear reuse pathway.
    * **REMEDIATE** -- integrity at/above ``_REMEDIATE_MIN_INTEGRITY`` and at
      least one application is ``CONDITIONAL`` or ``SUITABLE``: deficiencies are
      fixable and a reuse pathway is plausible after work.
    * **MONITOR** -- the remaining case: the well is not an immediate abandon
      candidate but has no current reuse pathway; periodic surveillance applies.

    Args:
        integrity: Integrity result for the well.
        risk: Risk result for the well.
        co2: CO2 storage suitability level.
        geothermal: Geothermal suitability level.

    Returns:
        ``(verdict, trace)`` with the chosen verdict and the decisive reason.
    """
    i = integrity.overall_integrity_score
    r = risk.risk_score
    any_suitable = SuitabilityLevel.SUITABLE in (co2, geothermal)
    any_conditional_or_better = any_suitable or SuitabilityLevel.CONDITIONAL in (
        co2,
        geothermal,
    )

    if i < _ABANDON_MAX_INTEGRITY or r >= _ABANDON_MIN_RISK:
        verdict = Verdict.ABANDON
        reason = (
            f"integrity {i} below {_ABANDON_MAX_INTEGRITY} "
            f"or risk {r} at/above {_ABANDON_MIN_RISK}"
        )
    elif i >= _REUSE_MIN_INTEGRITY and r <= _REUSE_MAX_RISK and any_suitable:
        verdict = Verdict.REUSE
        reason = (
            f"integrity {i} >= {_REUSE_MIN_INTEGRITY}, risk {r} <= {_REUSE_MAX_RISK}, "
            "and at least one application is suitable"
        )
    elif i >= _REMEDIATE_MIN_INTEGRITY and any_conditional_or_better:
        verdict = Verdict.REMEDIATE
        reason = (
            f"integrity {i} >= {_REMEDIATE_MIN_INTEGRITY} and a reuse pathway is "
            "plausible after remediation"
        )
    else:
        verdict = Verdict.MONITOR
        reason = "no immediate abandon trigger and no current reuse pathway"

    trace = {
        "verdict": verdict.value,
        "reason": reason,
        "inputs": {
            "integrity_score": i,
            "risk_score": r,
            "co2_suitability": co2.value,
            "geothermal_suitability": geothermal.value,
            "any_suitable": any_suitable,
            "any_conditional_or_better": any_conditional_or_better,
        },
        "policy": {
            "reuse_min_integrity": _REUSE_MIN_INTEGRITY,
            "reuse_max_risk": _REUSE_MAX_RISK,
            "remediate_min_integrity": _REMEDIATE_MIN_INTEGRITY,
            "abandon_max_integrity": _ABANDON_MAX_INTEGRITY,
            "abandon_min_risk": _ABANDON_MIN_RISK,
        },
    }
    return verdict, trace


def generate_required_actions(
    well: WellData,
    integrity: IntegrityResult,
    risk: RiskResult,
    *,
    has_verified_secondary: bool,
    primary_failed_or_unverified: bool,
    co2_trace: dict[str, Any],
    geothermal_trace: dict[str, Any],
) -> tuple[tuple[str, ...], dict[str, Any]]:
    """Derive a de-duplicated, ordered list of required engineering actions.

    Actions are driven by the integrity findings, the risk level, and the gates
    that failed during suitability screening, so each action is traceable to a
    concrete deficiency.

    Args:
        well: The well under assessment.
        integrity: Integrity result for the well.
        risk: Risk result for the well.
        has_verified_secondary: Whether a verified secondary barrier exists.
        primary_failed_or_unverified: Whether the primary envelope is unreliable.
        co2_trace: The CO2 suitability gate trace.
        geothermal_trace: The geothermal suitability gate trace.

    Returns:
        ``(actions, trace)`` where ``actions`` is an ordered, de-duplicated
        tuple and ``trace`` records the reasons that produced each action.
    """
    reasons: list[tuple[str, str]] = []  # (action, reason)

    if primary_failed_or_unverified:
        reasons.append(
            ("Verify or repair the primary (source-facing) barrier.",
             "primary barrier failed or unverified")
        )
    if not has_verified_secondary:
        reasons.append(
            ("Verify the independent secondary barrier.",
             "no verified independent secondary barrier")
        )
    if integrity.cement_quality_score < 60.0:
        reasons.append(
            ("Perform a cement bond log (CBL/USIT) to confirm annular seal.",
             f"cement quality score {integrity.cement_quality_score} below adequate")
        )
    if integrity.mechanical_integrity_score < 60.0:
        reasons.append(
            ("Run pressure / mechanical integrity testing on casing and tubing.",
             f"mechanical integrity score {integrity.mechanical_integrity_score} below adequate")
        )
    if well.is_abandoned and integrity.plugging_score < 40.0:
        reasons.append(
            ("Re-evaluate and, if required, re-establish abandonment plugs.",
             f"plugging score {integrity.plugging_score} inadequate for an abandoned well")
        )
    if risk.risk_score >= 51.0:
        reasons.append(
            ("Investigate potential leakage pathways and pressure anomalies.",
             f"risk score {risk.risk_score} in the high/critical band")
        )

    # Missing-data action driven by the data-uncertainty factor in the risk
    # extraction trace, when available.
    extraction = risk.calculation_trace.get("factor_extraction", {}) if isinstance(
        risk.calculation_trace, dict
    ) else {}
    missing = extraction.get("data_uncertainty_missing_fields", {})
    missing_fields = [k for k, is_missing in missing.items() if is_missing]
    if missing_fields:
        reasons.append(
            (f"Collect missing well data: {', '.join(sorted(missing_fields))}.",
             "key characterisation fields are missing")
        )

    # Suitability-gate-driven actions (deduplicated naturally by the set below).
    for app_trace in (co2_trace, geothermal_trace):
        for gate in app_trace.get("gates", []):
            if gate["passed"]:
                continue
            name = gate["gate"]
            if name == "min_caprock_barrier_condition":
                reasons.append(
                    ("Assess and remediate caprock cement before CO2 storage reuse.",
                     "caprock condition below CO2 storage gate")
                )
            elif name == "min_temperature_c":
                reasons.append(
                    ("Confirm reservoir temperature; thermal resource may be insufficient.",
                     "temperature below geothermal gate")
                )
            elif name == "min_depth_m":
                reasons.append(
                    ("Confirm total depth against reuse depth requirements.",
                     "depth below a reuse gate")
                )

    # De-duplicate actions while preserving first-seen order.
    seen: set[str] = set()
    ordered_actions: list[str] = []
    action_reasons: dict[str, str] = {}
    for action, reason in reasons:
        if action not in seen:
            seen.add(action)
            ordered_actions.append(action)
            action_reasons[action] = reason

    trace = {"action_count": len(ordered_actions), "action_reasons": action_reasons}
    return tuple(ordered_actions), trace


def compute_confidence(
    risk: RiskResult,
    integrity: IntegrityResult,
) -> tuple[float, dict[str, Any]]:
    """Compute the confidence in the recommendation, reduced by uncertainty.

    Confidence begins at :data:`_CONFIDENCE_CEILING` and is reduced by:

    * the data-uncertainty fraction (fraction of key fields missing, taken from
      the risk calculation trace) scaled by :data:`_UNCERTAINTY_WEIGHT`, and
    * a per-flag penalty for each integrity flag, capped at
      :data:`_MAX_FLAG_PENALTY`.

    The result is clamped to ``[_CONFIDENCE_FLOOR, _CONFIDENCE_CEILING]``.

    Args:
        risk: Risk result (source of the data-uncertainty fraction).
        integrity: Integrity result (source of the flag count).

    Returns:
        ``(confidence, trace)`` with confidence in [0, 1] and the derivation.
    """
    extraction = risk.calculation_trace.get("factor_extraction", {}) if isinstance(
        risk.calculation_trace, dict
    ) else {}
    uncertainty_fraction = float(extraction.get("data_uncertainty_fraction", 0.0))

    flag_count = len(integrity.flags)
    flag_penalty = min(flag_count * _PER_FLAG_PENALTY, _MAX_FLAG_PENALTY)
    uncertainty_penalty = uncertainty_fraction * _UNCERTAINTY_WEIGHT

    raw = _CONFIDENCE_CEILING - uncertainty_penalty - flag_penalty
    confidence = max(_CONFIDENCE_FLOOR, min(_CONFIDENCE_CEILING, raw))

    trace = {
        "ceiling": _CONFIDENCE_CEILING,
        "floor": _CONFIDENCE_FLOOR,
        "data_uncertainty_fraction": round_score(uncertainty_fraction),
        "uncertainty_penalty": round_score(uncertainty_penalty),
        "integrity_flag_count": flag_count,
        "flag_penalty": round_score(flag_penalty),
        "raw_confidence": round_score(raw),
        "confidence": round_score(confidence),
    }
    return round_score(confidence), trace


def _compose_rationale(
    well: WellData,
    integrity: IntegrityResult,
    risk: RiskResult,
    verdict: Verdict,
    co2: SuitabilityLevel,
    geothermal: SuitabilityLevel,
    actions: tuple[str, ...],
    confidence: float,
) -> str:
    """Compose a human-readable rationale string.

    Args:
        well: The well under assessment.
        integrity: Integrity result.
        risk: Risk result.
        verdict: Chosen verdict.
        co2: CO2 suitability level.
        geothermal: Geothermal suitability level.
        actions: Required actions.
        confidence: Confidence score.

    Returns:
        A concise, multi-sentence rationale suitable for reports and UIs.
    """
    parts: list[str] = []
    parts.append(
        f"Well '{well.well_id}' has an overall integrity score of "
        f"{integrity.overall_integrity_score:.1f}/100 "
        f"({integrity.integrity_category.value}) and a risk score of "
        f"{risk.risk_score:.1f}/100 ({risk.risk_category.value})."
    )
    if risk.dominant_risk_drivers:
        parts.append(
            "Dominant risk drivers: "
            + ", ".join(risk.dominant_risk_drivers).replace("_", " ")
            + "."
        )
    parts.append(
        f"The engineering verdict is to {verdict.value.upper()}."
    )
    parts.append(
        f"Reuse screening: CO2 storage is {co2.value.replace('_', ' ')}; "
        f"geothermal is {geothermal.value.replace('_', ' ')}."
    )
    if actions:
        parts.append(
            f"{len(actions)} action(s) are required before the situation can "
            "improve, beginning with: " + actions[0]
        )
    else:
        parts.append("No remedial actions are required.")
    parts.append(f"Confidence in this recommendation is {confidence:.2f}.")
    return " ".join(parts)


def assess_recommendations_traced(
    well: WellData,
    integrity: IntegrityResult,
    risk: RiskResult,
    *,
    has_verified_secondary: bool,
    primary_failed_or_unverified: bool,
) -> tuple[RecommendationResult, dict[str, Any]]:
    """Produce a recommendation and its full calculation trace.

    This is the primary public entry point. It is a pure, deterministic
    function of its inputs and the externalised ``co2_storage`` / ``geothermal``
    configuration; it never mutates its inputs.

    The two barrier predicates are passed in explicitly (rather than recomputed)
    so that the recommendation engine stays decoupled from the integrity
    engine's internals while remaining consistent with the integrity result the
    caller already produced. The pipeline obtains them from
    :func:`lwra.integrity_engine.has_verified_secondary_barrier` and
    :func:`lwra.integrity_engine.primary_is_failed_or_unverified`.

    Args:
        well: The well under assessment.
        integrity: Integrity result for the same well.
        risk: Risk result for the same well.
        has_verified_secondary: Whether a verified secondary barrier exists.
        primary_failed_or_unverified: Whether the primary envelope is unreliable.

    Returns:
        ``(result, trace)``. The ``trace`` is the complete, nested derivation
        suitable for audit, publication appendices, JSON reports, and as a
        feature source for future machine-learning augmentation.

    Raises:
        ValueError: If ``well``, ``integrity`` and ``risk`` do not all refer to
            the same well.
    """
    if not (well.well_id == integrity.well_id == risk.well_id):
        raise ValueError(
            "well, integrity and risk must refer to the same well "
            f"({well.well_id!r}, {integrity.well_id!r}, {risk.well_id!r})."
        )

    co2_level, co2_trace = assess_co2_storage_suitability(
        well, integrity, risk, has_verified_secondary=has_verified_secondary
    )
    geo_level, geo_trace = assess_geothermal_suitability(
        well, integrity, risk, has_verified_secondary=has_verified_secondary
    )

    verdict, verdict_trace = decide_verdict(integrity, risk, co2_level, geo_level)

    actions, actions_trace = generate_required_actions(
        well,
        integrity,
        risk,
        has_verified_secondary=has_verified_secondary,
        primary_failed_or_unverified=primary_failed_or_unverified,
        co2_trace=co2_trace,
        geothermal_trace=geo_trace,
    )

    confidence, confidence_trace = compute_confidence(risk, integrity)

    rationale = _compose_rationale(
        well, integrity, risk, verdict, co2_level, geo_level, actions, confidence
    )

    result = RecommendationResult(
        well_id=well.well_id,
        verdict=verdict,
        co2_storage_suitability=co2_level,
        geothermal_suitability=geo_level,
        required_actions=actions,
        confidence=confidence,
        rationale=rationale,
    )

    trace: dict[str, Any] = {
        "well_id": well.well_id,
        "predicates": {
            "has_verified_secondary_barrier": has_verified_secondary,
            "primary_failed_or_unverified": primary_failed_or_unverified,
        },
        "co2_storage": co2_trace,
        "geothermal": geo_trace,
        "verdict": verdict_trace,
        "required_actions": actions_trace,
        "confidence": confidence_trace,
        "rationale": rationale,
    }
    return result, trace


def assess_recommendations(
    well: WellData,
    integrity: IntegrityResult,
    risk: RiskResult,
    *,
    has_verified_secondary: bool,
    primary_failed_or_unverified: bool,
) -> RecommendationResult:
    """Produce a recommendation for a single well.

    Convenience wrapper over :func:`assess_recommendations_traced` that discards
    the trace. See that function for the full contract.

    Args:
        well: The well under assessment.
        integrity: Integrity result for the same well.
        risk: Risk result for the same well.
        has_verified_secondary: Whether a verified secondary barrier exists.
        primary_failed_or_unverified: Whether the primary envelope is unreliable.

    Returns:
        A fully populated, immutable :class:`RecommendationResult`.
    """
    result, _ = assess_recommendations_traced(
        well,
        integrity,
        risk,
        has_verified_secondary=has_verified_secondary,
        primary_failed_or_unverified=primary_failed_or_unverified,
    )
    return result
