# Scientific & Engineering Review — Legacy Well Risk Assessment Tool

**Review date:** 2026-06-25
**Scope:** Computational core (`models`, `config`, `integrity_engine`,
`risk_engine`, `recommendation_engine`, `services`) and the
`risk_engine.robustness` capability added in this review.

Honest audit. Assumptions tagged **[P]** physically justified, **[L]**
literature/standard-derived, **[E]** engineering judgement, **[A]** arbitrary.
No claims or references invented. The tool already states it is *inspired by* but
**not compliant with** API RP 90 / NORSOK D-010 / ISO 27914 — that framing is
correct and is preserved here.

---

## 1. Purpose and validity envelope

LWRA scores the integrity and leakage risk of *legacy/abandoned* wells from
sparse archive data and ranks a portfolio for remediation / P&A / reuse triage.
It is a **screening and prioritisation** tool, not a barrier-verification record
or a regulatory compliance engine. It does not model transient pressure,
cement-bond physics, or corrosion kinetics. The barrier-based scoring is a
semi-quantitative encoding of two-barrier philosophy, which is the appropriate
altitude for portfolio triage.

## 2. Assumption classification

| Assumption | Value | Tag | Notes |
|---|---|---|---|
| Two-barrier philosophy (primary + verified secondary required) | — | **[L]** | Core of NORSOK D-010 / risk-based well integrity. Encoded as hard caps. |
| Missing verified secondary → integrity cap | 59 | **[L]/[E]** | Direction is standard; the exact cap is judgement. |
| Failed/unverified primary → integrity cap | 39 | **[L]/[E]** | As above. |
| Unverified-barrier trust discount | ×0.60 | **[E]/[A]** | "Unverified ≠ credited" is sound; the 0.60 magnitude is arbitrary. Hard-coded in Python (W1). |
| Verified-but-low-confidence discount | ×0.80 | **[E]/[A]** | Sound direction; magnitude arbitrary. Hard-coded (W1). |
| Low-confidence condition threshold | 0.40 | **[E]** | In YAML (`integrity_overrides`). Good. |
| Primary "failed" condition | ≤0.40 | **[E]/[A]** | Hard-coded in `barrier_eval` (W1) and duplicates the YAML low-confidence value conceptually. |
| Risk category bands | 0/26/51/76 | **[E]** | Quartile-aligned; documented. Reasonable. |
| Factor normalisation anchors (age 60 yr, pressure 600 bar, temp 20–200 °C, proximity 100 m–5 km) | — | **[E]/[L]** | Ranges track HPHT/legacy-well experience; exact anchors are judgement, all in YAML. |
| `default_when_unknown` contributions (40–60) | — | **[E]** | Conservative mid-high defaults for missing inputs. Appropriately documented. |
| Risk factor / likelihood-consequence weights | — | **[E]** | Validated to sum to 1.0 at load (good). Magnitudes are judgement. |
| Fluid hazard scores | — | **[E]** | Ordinal hazard ranking; defensible order, arbitrary gaps. |
| BHT/CO₂/geothermal forward gates | 800 m, 70/85, etc. | **[L]** | Mirror cssd/gsp screening thresholds; consistent across the project family. |
| Risk-category robustness band max | 15 pts | **[E]/[A]** | New. Scales with data-uncertainty fraction. Calibrate against back-tested re-assessments. |

**Arbitrary items to challenge first:** the two verification discounts (0.60,
0.80) and the new 15-point robustness band.

## 3. Methodology findings

* **Normalisation** is linear and monotonic with clamped bounds and a guarded
  degenerate ramp (`high == low` raises) — now covered by unit tests
  (`test_core_scoring.py`).
* **Axis renormalisation** (`weighted_axis_score`) correctly divides by the
  total axis weight so likelihood/consequence stay on a true 0–100 scale despite
  factors splitting weight — a subtle, correct touch.
* **Interval coverage** uses a proper merge-then-clip so overlapping intervals
  are not double-counted (tested).
* **No uncertainty on the category → addressed.** A point risk score hid whether
  a well sat safely inside a band or on a boundary. `risk_engine.robustness`
  now brackets the score by a data-uncertainty-derived band and flags whether
  the *category* survives, without altering the nominal score. Deterministic.
* **Determinism.** Pure functions over cached YAML; `as_of` is injectable so
  age-based scoring is reproducible. Verified by existing pipeline tests.

## 4. Engineering review & weaknesses

| ID | Severity | Finding |
|---|---|---|
| **W1** | Medium | The module docstrings state "nothing is hard-coded in Python", but the verification discounts (`_UNVERIFIED_DISCOUNT=0.60`, `_LOW_CONFIDENCE_DISCOUNT=0.80` in `_scoring.py`) and `_PRIMARY_FAILED_CONDITION=0.40` (in `barrier_eval.py`) **are** hard-coded. These are scientifically meaningful, arbitrary parameters and belong in `weights.yaml`/`thresholds.yaml`. Documented rather than refactored here to avoid changing scored outputs without a coordinated trace-test update; this is the top remaining refactor. |
| **W2** | Low | `_PRIMARY_FAILED_CONDITION` (0.40) and `low_confidence_condition_threshold` (0.40, YAML) are conceptually linked but defined in two places; they can silently diverge. Consolidate to the single YAML key. |
| **W3** | Low | Thinner test suite than the sibling projects: the scoring *primitives* lacked direct unit tests. **Partly addressed** this review (`test_core_scoring.py`, `test_robustness.py`); the integrity aggregator and recommendation engine still warrant dedicated unit tests. |
| **W4** | Info | A stray duplicate package tree exists at `mnt/user-data/outputs/legacy-well-risk-assessment/src/lwra/__init__.py` — packaging artefact that should be removed from version control. |

The new `risk_engine.robustness` module is clean under `ruff` and
`mypy --strict`; the full suite (now 44 tests) passes.

## 5. References — adequacy and gaps

The literature foundation (root `Elicit — …` summary and `docs/references.md`)
cites the right standards (API RP 90, NORSOK D-010, ISO 27914) with the correct
*non-compliance* caveat. Honest gaps (recommended, **not** fabricated):

* **Recommended standard** — the verification-discount model (W1) is consistent
  with NORSOK D-010 well-barrier-element acceptance but no clause is cited for
  the specific 0.60/0.80 magnitudes; either cite a basis or keep them flagged as
  pure judgement (current honest position).
* **Academic literature** — legacy-well leakage likelihood vs age/abandonment
  practice (e.g. Davies et al., 2014, *Oil and gas wells and their integrity*;
  Watson & Bachu, SPE 106817) would ground the age and barrier-failure factors.
* **Insufficient evidence** — fluid-hazard ordinal scores have no single citable
  source; they are judgement and labelled as such.

## 6. Prioritised roadmap

1. **(Done)** Risk-category robustness under data-uncertainty band, with config,
   tests, and docs; doubled the core unit-test coverage.
2. **(Medium, next)** Externalise W1 constants to YAML and consolidate W2; update
   trace-assertion expectations in lock-step. Backward-compatible numerically.
3. **(Low)** Add aggregator and recommendation-engine unit tests (W3).
4. **(Low)** Remove the stray duplicate package tree (W4).
5. **(Portfolio)** Add the well-integrity literature references (§5).

## 7. Portfolio assessment

Strengths for CCS / well-integrity / digital-subsurface roles: a faithful
encoding of two-barrier philosophy with hard-cap overrides, fully externalised
and weight-validated configuration, complete auditable traces, and forward-
looking CO₂/geothermal reuse gates that tie this tool into the sibling
screening projects (cssd, gsp). The added category-robustness layer signals
maturity about decision uncertainty. The honest *inspired-by-not-compliant-with*
standards framing is a credibility asset; the main gap is closing W1 and
expanding unit coverage of the integrity aggregator.
