# Methodology

> **Advisory notice.** LWRA's methodology is inspired by API RP 90,
> NORSOK D-010, and ISO 27914. It does **not** claim official compliance with
> any standard. Results are advisory and must be reviewed by a qualified
> well-integrity engineer before any operational decision.

## 1. Integrity assessment

The integrity engine scores five well-barrier components on a 0–100 scale
(100 = perfect integrity) and aggregates them into an overall integrity score.

### 1.1 Component scoring

| Component | What is measured | Key inputs |
|---|---|---|
| **Primary barrier** | Source-facing envelope (cement + casing at reservoir) | Condition score, verification status, interval coverage |
| **Secondary barrier** | Independent backup envelope | Same as primary |
| **Cement quality** | Annular seal continuity across caprock | Condition × coverage modifier |
| **Mechanical integrity** | Load-bearing / pressure-containing hardware | Casing, tubing, packer, wellhead conditions |
| **Plugging** | Abandonment plug competence | Condition × length-adequacy modifier |

Each component's raw condition score (0–1, measured or estimated) is
converted to a 0–100 score through a verification-discounted model:
unverified barriers attract a configurable penalty before the score is
scaled.

### 1.2 Weighted aggregation

Component scores are combined using the weights in `weights.yaml:
integrity_component_weights`. Default weights (sum = 1.0):

| Component | Weight | Rationale |
|---|---|---|
| Primary barrier | 0.30 | Most consequential single failure mode |
| Cement quality | 0.25 | Annular seal is the second critical path |
| Secondary barrier | 0.20 | Independent backup is mandatory |
| Mechanical integrity | 0.15 | Hardware failure is secondary stressor |
| Plugging | 0.10 | Governing long-term barrier for abandoned wells |

### 1.3 Override caps (well-barrier philosophy)

Two hard caps enforce two-barrier logic regardless of the weighted score:

- **No verified independent secondary barrier** → cap at 59.0 (top of *poor*)
- **Failed or unverified primary barrier** → cap at 39.0 (top of *failed*)

The most restrictive applicable cap wins.

### 1.4 Integrity categories

| Category | Score range |
|---|---|
| Good | 80–100 |
| Moderate | 60–79 |
| Poor | 40–59 |
| Failed | 0–39 |

---

## 2. Risk assessment

The risk engine combines seven factors into a 0–100 risk score (100 = highest
risk) and places the well in a 5×5 likelihood × consequence risk matrix.

### 2.1 Factor normalisation

Each factor is normalised to a 0–100 risk contribution before weighting, using
linear interpolation between `low` and `high` bounds in `thresholds.yaml:
factor_normalisation`. Special cases:

- `integrity_score`: inverted — higher integrity → lower risk contribution.
- `proximity_to_receptors`: inverted — closer distance → higher risk.
- `fluid_hazard`: table lookup from `weights.yaml: fluid_hazard_scores`.
- Missing values use a conservative `default_when_unknown`.

### 2.2 Risk factors and weights

Default weights (sum = 1.0):

| Factor | Weight | Axis split (L / C) |
|---|---|---|
| Integrity score | 0.35 | 85 / 15 |
| Fluid hazard | 0.18 | 10 / 90 |
| Proximity to receptors | 0.17 | 5 / 95 |
| Reservoir pressure | 0.12 | 60 / 40 |
| Well age | 0.08 | 90 / 10 |
| Temperature | 0.05 | 70 / 30 |
| Data uncertainty | 0.05 | 50 / 50 |

The likelihood and consequence axis scores are computed by splitting each
factor's weighted contribution according to the L/C ratios, then clamping
the sums to [0, 100].

### 2.3 Risk categories

| Category | Score range |
|---|---|
| Low | 0–25 |
| Medium | 26–50 |
| High | 51–75 |
| Critical | 76–100 |

---

## 3. Recommendation engine

### 3.1 Engineering verdict

The verdict is determined by thresholds on the overall integrity and risk scores:

| Verdict | Condition |
|---|---|
| **Reuse** | Integrity ≥ 80 and risk ≤ 25 |
| **Remediate** | Integrity ≥ 40 and not Reuse |
| **Monitor** | Integrity ≥ 40 and risk borderline |
| **Abandon** | Integrity < 40 or risk ≥ 76 |

### 3.2 CO2 storage suitability (ISO 27914-inspired)

Gate-based screening against `thresholds.yaml: co2_storage`:

| Gate type | Gate | Default threshold |
|---|---|---|
| Hard (any failure → UNSUITABLE) | Overall integrity | ≥ 70.0 |
| Hard | Risk score | ≤ 50.0 |
| Hard | Verified secondary barrier | Required |
| Hard | Caprock barrier condition | ≥ 0.70 (raw 0–1) |
| Hard | Total depth | ≥ 800 m (supercritical CO2 depth) |
| Preferred (all met → SUITABLE) | Overall integrity | ≥ 85.0 |

### 3.3 Geothermal suitability

Same gate framework against `thresholds.yaml: geothermal`, with lower
containment stringency but temperature and depth requirements:

| Gate type | Gate | Default threshold |
|---|---|---|
| Hard | Overall integrity | ≥ 55.0 |
| Hard | Risk score | ≤ 65.0 |
| Hard | Temperature | ≥ 60 °C (direct-use lower bound) |
| Hard | Depth | ≥ 1000 m |
| Preferred | Overall integrity | ≥ 75.0 |
| Preferred | Temperature | ≥ 120 °C (power-generation target) |

### 3.4 Confidence

Confidence in the recommendation decays from a ceiling (0.98) based on the
data-uncertainty factor from the risk engine and the number of integrity flags
raised. The floor is 0.20 so no recommendation is issued with zero confidence.
