# Architecture

## Overview

LWRA is a pure-Python, deterministic assessment pipeline. Every component is a
stateless function of its inputs and the externalised YAML configuration; the
only non-deterministic input is "today" (used to age a well), which is always
passed explicitly so results are byte-for-byte reproducible.

```
WellData  (Pydantic v2, frozen)
  │
  ├─► integrity_engine.assess_integrity_traced
  │       └─► IntegrityResult  (0-100 overall + five components + flags)
  │
  ├─► risk_engine.assess_risk_traced
  │       └─► RiskResult  (0-100 score + likelihood/consequence + drivers)
  │
  └─► recommendation_engine.assess_recommendations_traced
          └─► RecommendationResult  (verdict + CO2/geothermal suitability + actions)
                │
                └─► WellAssessment  (immutable bundle, the public contract)
```

## Package layout

```
src/lwra/
├── models/                 Pydantic v2 input and result contracts (frozen)
│   ├── enums.py            Domain enumerations (BarrierType, FluidType, …)
│   ├── barrier.py          BarrierData, CasingString
│   ├── well.py             WellData (top-level input)
│   └── results.py          IntegrityResult, RiskResult, RecommendationResult
│
├── config/                 Externalised weights and thresholds
│   ├── enums.py            Config-key enumerations (RiskFactor, IntegrityComponent)
│   ├── weights.yaml        Component and factor weights
│   └── thresholds.yaml     Category boundaries, overrides, screening criteria
│
├── integrity_engine/       Five-component barrier-philosophy engine
│   ├── _scoring.py         Shared helpers (condition-to-score, penalties, rounding)
│   ├── barrier_eval.py     Primary and secondary barrier scoring
│   ├── cement.py           Cement quality (condition × coverage)
│   ├── mechanical.py       Casing / tubing / packer / wellhead
│   ├── plugging.py         Abandonment plug condition and length adequacy
│   └── aggregator.py       Weighted aggregation + override caps (public entry point)
│
├── risk_engine/            Factor-based risk scoring engine
│   ├── weighting.py        Factor normalisation, YAML loaders, likelihood/consequence split
│   ├── categories.py       RiskCategory assignment and 5×5 matrix binning
│   └── scorer.py           Aggregation and public entry point
│
├── recommendation_engine/  Verdict and reuse-suitability engine
│   ├── _config.py          Thresholds loader + rounding helper
│   └── recommender.py      Gate-based CO2/geothermal screening, verdict, actions
│
├── services/
│   └── pipeline.py         Single orchestration seam → WellAssessment
│
├── visualizations/         Plotly chart builders
│   ├── _theme.py           Colour vocabulary and shared layout defaults
│   ├── gauges.py           Integrity and risk score dials
│   ├── radar.py            Five-component radar chart
│   ├── heatmap.py          5×5 risk-matrix heatmap
│   └── bars.py             Weighted risk contributions and portfolio bars
│
├── reports/                Serialisation layer
│   ├── _common.py          Shared path resolution, trace flattening, formatting
│   ├── json_report.py      Lean or fully traced JSON
│   ├── excel_report.py     Multi-sheet OpenPyXL workbook
│   └── pdf_report.py       Publication-quality ReportLab PDF
│
├── api/
│   └── main.py             Thin FastAPI transport boundary
│
├── dashboard/
│   └── app.py              Streamlit presentation layer
│
└── sample_data.py          Canonical synthetic wells for examples and tests
```

## Design principles

**Immutability.** All data models (`WellData`, result types, `WellAssessment`)
are `frozen=True` Pydantic models. Engines consume them and produce *new*
objects; no mutation ever occurs in the computation path.

**Determinism.** The only source of non-determinism is `date.today()`, which
is always threaded in as an explicit `as_of` argument. Numeric results are
rounded to a fixed precision (`ROUNDING_DP = 2`) so scores are byte-for-byte
stable across runs.

**Separation of concerns.** The three engines are pure functions with no
knowledge of each other. `services.pipeline` is the only module that wires
them together. Downstream consumers (API, dashboard, report writers) import
only from `services.pipeline` and `models.*`.

**Externalised configuration.** All weights, thresholds, and screening
criteria live in `config/weights.yaml` and `config/thresholds.yaml`. They are
loaded once per process via `functools.lru_cache` and are tunable without code
changes — a prerequisite for methodology transparency and regulatory review.

**Full traceability.** Every `*_traced` function returns its result together
with a `calculation_trace` dict that records every intermediate value, weight,
and decision rule used to produce the score. Reports can embed this trace in
full, suiting publication appendices and database archiving.
