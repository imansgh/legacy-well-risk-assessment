# Legacy Well Risk Assessment Tool (LWRA)

Evaluates the integrity and reuse potential of legacy oil and gas wells for
applications such as **CO₂ storage** and **geothermal energy**.

Methodology is inspired by **API RP 90, NORSOK D-010, ISO 27914**, and
well-barrier and risk-based principles. **This tool does not claim official
compliance with any standard; results are advisory** and must be reviewed by a
qualified well-integrity engineer before any operational decision.

---

## What it does

Given a structured description of a well (its barriers, casing, fluids, depth,
and surroundings), LWRA produces a fully traceable assessment:

```
WellData
  → IntegrityResult        (barrier, cement, mechanical, plugging scores + overall)
  → RiskResult             (likelihood × consequence, 0–100, risk-matrix cell)
  → RecommendationResult   (verdict + CO₂/geothermal suitability + actions)
  → WellAssessment         (the bundled, immutable output)
```

Every score carries a calculation trace, so any number in a report can be traced
back to the inputs, weights, and thresholds that produced it.

## Architecture

```
src/lwra/
├── models/                 # Pydantic v2 data contracts (frozen, validated)
├── config/                 # weights.yaml, thresholds.yaml + config-key enums
├── integrity_engine/       # primary/secondary/cement/mechanical/plugging + aggregation
├── risk_engine/            # factor normalisation, weighting, categories, matrix
├── recommendation_engine/  # verdict, CO₂/geothermal screening, actions, confidence
├── services/pipeline.py    # the single orchestration seam → WellAssessment
├── visualizations/         # Plotly gauges, radar, risk-matrix heatmap, bars
├── reports/                # PDF (ReportLab), Excel (OpenPyXL), JSON
├── api/                    # FastAPI backend
├── dashboard/              # Streamlit app
└── sample_data.py          # canonical example wells
```

The engines are **pure, deterministic functions**. The only non-deterministic
input is "today" (used to age a well); pass an explicit `as_of` date for fully
reproducible output. All weights and thresholds live in YAML and are tunable
without code changes.

## Installation

```bash
pip install -e ".[all,dev]"     # everything + test toolchain
# or a subset:
pip install -e ".[api]"         # core + FastAPI
pip install -e ".[dashboard]"   # core + Streamlit
```

Core (models + engines + pipeline) needs only `pydantic` and `PyYAML`.

## Usage

### Library

```python
from datetime import date
from lwra.sample_data import remediation_well
from lwra.services.pipeline import assess_well_traced

assessment = assess_well_traced(remediation_well(), as_of=date(2025, 1, 1))
print(assessment.verdict, assessment.risk_score, assessment.overall_integrity_score)
```

### Examples

```bash
python examples/assess_single_well.py     # one well + JSON/Excel/PDF reports
python examples/screen_portfolio.py        # batch screening + summary CSV
```

### API

```bash
uvicorn lwra.api.main:app --reload
# POST /assess, POST /assess/batch, POST /report/{json|excel|pdf}, GET /config
# Interactive docs at http://localhost:8000/docs
```

### Dashboard

```bash
streamlit run src/lwra/dashboard/app.py
```

## Tests

```bash
pytest                 # full suite
pytest --cov=lwra      # with coverage
```

## Reproducibility & auditability

- Scores are rounded to a fixed precision and computed from cached, immutable
  config, so results are byte-for-byte reproducible for a given `as_of`.
- `assess_well_traced` returns the complete derivation; the JSON/Excel reports
  can embed it, suiting publication appendices and database archiving.

## License

MIT.
