# Limitations

LWRA is a screening tool, not a site-specific engineering analysis. This page
documents the boundaries of what the tool can and cannot reliably assess.
Reviewers and end users should read this document before relying on any output
for operational or regulatory decisions.

---

## Scope limitations

**Advisory results only.** All outputs — integrity scores, risk scores,
suitability levels, and verdicts — are advisory. They must be reviewed and
validated by a qualified well-integrity engineer before any operational
decision (intervention, injection, monitoring plan, regulatory notification)
is made.

**No field-data integration.** LWRA does not connect to well databases,
wireline log archives, or downhole pressure monitoring systems. Condition
scores must be supplied by the analyst, who is responsible for translating raw
data (e.g. CBL quality, caliper surveys, pressure test results) into the 0–1
range expected by the model.

**No time-series modelling.** The assessment is a snapshot at the `as_of`
date. Progressive degradation, creep, corrosion growth rates, or remediation
effectiveness over time are not modelled. Repeated assessments at different
`as_of` dates must be compared manually.

**Two-dimensional risk matrix only.** The 5×5 likelihood × consequence matrix
is a standard industry visualisation tool. It does not replace quantitative
risk analysis (QRA) for high-consequence facilities or regulatory submissions
that require frequency-based risk estimates.

---

## Geological and reservoir limitations

**No subsurface pathway modelling.** LWRA does not model fault connectivity,
caprock integrity, or preferential flow paths. A well with high integrity may
still pose a leakage risk if it intersects a permeable fault zone; conversely,
a well with moderate integrity in a tight formation may pose little actual risk.

**Static reservoir properties.** Pressure, temperature, and fluid type are
treated as static inputs. Pressure depletion, thermal effects of injection, or
fluid phase changes are not captured.

**Depth as a surrogate for CO2 phase.** The `min_depth_m` gate for CO2
storage uses depth as a proxy for supercritical conditions. In practice,
the pressure–temperature gradient must be assessed site-specifically.

---

## Data quality limitations

**Garbage in, garbage out.** Condition scores of 1.0 for every barrier on a
1960s well with no documented inspection data will produce an optimistic
assessment. The data-uncertainty factor penalises *missing* fields but cannot
detect implausible values.

**No inter-element correlation.** If all barriers in a well share a common
failure mode (e.g. all installed in the same cement job by the same contractor
in the same year), the model treats them as independent. This may
underestimate correlated failure risk.

**Single representative condition score per barrier.** The model accepts one
condition score per barrier element. For elements with spatially varying
condition (e.g. corroded casing with good and poor sections), the analyst
must choose a representative value, ideally the minimum or a
length-weighted mean.

---

## Regulatory limitations

**Not a substitute for regulatory compliance.** National regulations governing
well plugging and abandonment, CO2 storage site licensing, or geothermal
drilling permits vary by jurisdiction and change over time. LWRA does not track
or enforce any specific regulatory framework.

**Standards are referenced, not implemented.** API RP 90, NORSOK D-010, and
ISO 27914 are referenced as methodological inspiration. The tool does not
implement, interpret, or certify compliance with any of these standards.

---

## Software limitations

**Python ≥ 3.12 required.** The package uses `tuple[…]` type annotations and
other syntax available only from Python 3.12 onward.

**Optional dependencies must be installed for full functionality.** The core
engines (models, config, integrity, risk, recommendation, pipeline) require
only `pydantic` and `PyYAML`. Visualisations (`plotly`), reports
(`reportlab`, `openpyxl`, `kaleido`), the API (`fastapi`, `uvicorn`), and the
dashboard (`streamlit`) must be installed separately — see the `[project.optional-dependencies]`
groups in `pyproject.toml`.

**Floating-point arithmetic.** Scores are rounded to two decimal places to
ensure reproducibility across platforms and Python versions. Sub-centesimal
differences between environments are possible before rounding.
