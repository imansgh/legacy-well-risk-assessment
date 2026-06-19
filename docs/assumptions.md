# Assumptions

This document records the modelling assumptions embedded in LWRA's default
configuration and scoring logic. Each assumption is stated explicitly so that
a reviewer, auditor, or methodology committee can evaluate and, where
necessary, override it through the externalised YAML configuration.

---

## Data model assumptions

**Single assessment date.** The `as_of` date is applied uniformly to age
every well in a portfolio. Cross-portfolio comparisons are only meaningful
when the same `as_of` is used for all wells.

**Observed barrier conditions are authoritative.** `BarrierData.condition_score`
(0–1) is treated as the single ground-truth observation for each barrier
element. LWRA does not model measurement uncertainty around this value; if
that is important, the caller should supply a conservative (lower) estimate.

**Barrier intervals are contiguous.** The cement coverage computation assumes
that a barrier element spans `[depth_top_m, depth_bottom_m]` without gaps.
Multiple elements of the same type (e.g. two cement plugs) are treated as
independent observations, not as a single merged interval.

**GeoLocation is the wellhead position.** `proximity_to_receptors_m` is
measured from the wellhead. For deviated wells, the horizontal distance to
a receptor from the bottom-hole location may differ significantly.

---

## Integrity engine assumptions

**Condition-to-score mapping is linear.** A raw condition score of 1.0 maps
to 100 and 0.0 maps to 0 after verification discounting. No non-linear
degradation curves are applied.

**Unverified barriers attract a penalty but are not zeroed.** An unverified
barrier with a high condition score will still contribute positively to the
component score, albeit at a reduced weight. The override cap (≤ 59 without
a verified secondary barrier) provides the hard floor.

**Cement coverage uses the barrier interval, not the caprock window.** When
no explicit caprock depth is supplied, the sealing interval is taken as the
span of the cement barrier elements themselves. This is conservative for
wells where the cement extends well above the caprock contact.

**Plugging: not-abandoned wells score at a neutral baseline.** A well without
an abandonment date and without plug elements is not penalised for absence of
plugs, because plugging is not yet expected. The aggregator may flag the
absence, but the score is not forced to zero.

**Mechanical integrity groups casing, tubing, packer, and wellhead.** These
four element types are scored together as the "mechanical integrity" component.
No distinction is made between surface and subsurface hardware within this
component.

---

## Risk engine assumptions

**Well age proxy.** Age is computed as years since spud date, or years since
abandonment date if recorded. If both dates are missing, a conservative default
(50 out of a 0–60 year normalisation range, mapping to ~83/100 contribution)
is used. This is intentionally pessimistic.

**Fluid hazard is static.** The reservoir fluid type is taken from `WellData`
and does not change over time. Fluid type changes due to production history,
injection, or natural processes are not modelled.

**Data uncertainty is field-completeness-based.** The uncertainty factor is
derived from the fraction of key `WellData` fields that are `None` or unknown.
This is a proxy for characterisation quality, not a formal epistemic
uncertainty quantification.

**Proximity to receptors is a point-to-point distance.** No directional or
geological pathway analysis is performed. The caller is responsible for
supplying a representative minimum distance to the most sensitive receptor.

**Reservoir pressure defaults to bar.** No unit conversion is performed.
The caller must supply pressure in bar to match the normalisation bounds
in `thresholds.yaml`.

---

## Recommendation engine assumptions

**Verdict thresholds are policy, not physics.** The integrity and risk
thresholds that determine the engineering verdict (reuse / remediate /
monitor / abandon) reflect a conservative policy position. They are embedded
in code rather than YAML to make them deliberate and visible, but they can be
overridden by subclassing or patching for deployments with different policies.

**CO2 screening is non-compliant with ISO 27914.** The gate-based CO2
suitability screening is *inspired* by ISO 27914 containment requirements but
is not a substitute for a formal site-specific conformance assessment.

**Geothermal screening ignores permeability and reservoir productivity.** The
geothermal suitability assessment considers temperature and depth as proxies
for usable thermal energy. Permeability, flow rate, and thermal recovery
factor are not modelled.

**Confidence is an ordinal indicator, not a calibrated probability.** The
confidence score (0–1) is a relative indicator of recommendation reliability,
not a calibrated probability that the verdict is correct. It should be
interpreted as: values closer to 1.0 indicate higher data completeness and
fewer integrity flags; values closer to 0.2 indicate the assessment rests on
very sparse or questionable data.
