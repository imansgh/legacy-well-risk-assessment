# Legacy Well Risk Assessment Tool (LWRA)

[![CI](https://github.com/imansgh/legacy-well-risk-assessment/actions/workflows/tests.yml/badge.svg)](https://github.com/imansgh/legacy-well-risk-assessment/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Integrity and reuse-potential screening for legacy oil and gas wells, targeting
**CO₂ storage** and **geothermal energy** applications.

Methodology is inspired by **API RP 90, NORSOK D-010, and ISO 27914**.
**This tool does not claim official compliance with any standard; results are
advisory** and must be reviewed by a qualified well-integrity engineer before
any operational decision.

---

## What it produces

Given a structured description of a well (barriers, casing, fluids, depth,
location, and surroundings), LWRA outputs a fully traceable assessment:

```
WellData
  → IntegrityResult       barrier · cement · mechanical · plugging → overall score (0–100)
  → RiskResult            likelihood × consequence → risk-matrix cell + score (0–100)
  → RecommendationResult  verdict · CO₂/geothermal suitability · required actions
  → WellAssessment        immutable bundle of all three results + optional trace
```

Every number in a report can be traced back to the exact inputs, weights, and
thresholds that produced it.

---

## Architecture

```
src/lwra/
├── models/                 # Pydantic v2 data contracts (frozen, validated)
├── config/                 # weights.yaml · thresholds.yaml · config-key enums
├── integrity_engine/       # primary · secondary · cement · mechanical · plugging
├── risk_engine/            # factor normalisation · weighting · matrix · categories
├── recommendation_engine/  # verdict · CO₂/geothermal screening · actions · confidence
├── services/pipeline.py    # single orchestration seam → WellAssessment
├── visualizations/         # Plotly gauges · radar · risk-matrix heatmap · bars
├── reports/                # JSON · Excel (OpenPyXL) · PDF (ReportLab)
├── api/                    # FastAPI backend
├── dashboard/              # Streamlit interactive app
└── sample_data.py          # four canonical example wells
```

Engines are **pure, deterministic functions**. The only non-deterministic input
is "today" (used to age a non-abandoned well); pass an explicit `as_of` date
for byte-for-byte reproducible output. All weights and thresholds live in YAML
and are tunable without code changes.

---

## Installation

```bash
# Full environment (recommended)
pip install -e ".[all,dev]"

# Subsets
pip install -e "."               # core only  (models + engines + pipeline)
pip install -e ".[api]"          # + FastAPI backend
pip install -e ".[dashboard,reports]"  # + Streamlit dashboard + report writers
pip install -e ".[dev]"          # + test/lint toolchain
```

> Core requires only `pydantic` and `PyYAML`.

---

## Quick start

### Python library

```python
from datetime import date
from lwra.sample_data import excellent_well
from lwra.services.pipeline import assess_well_traced

result = assess_well_traced(excellent_well(), as_of=date(2025, 1, 1))
print(result.verdict)                   # "reuse"
print(result.overall_integrity_score)   # e.g. 91.3
print(result.risk_score)                # e.g. 18.7

# How trustworthy is the risk *category*? The band scales with missing data.
from lwra.risk_engine.robustness import risk_category_robustness

rob = risk_category_robustness(
    excellent_well(), result.integrity, as_of=date(2025, 1, 1), risk=result.risk
)
print(rob.risk_category, rob.is_robust, rob.boundary_margin)
```

The methodology and an independent audit (assumption classification, weaknesses,
roadmap) are documented in
[`docs/methodology.md`](docs/methodology.md) and
[`docs/scientific_review.md`](docs/scientific_review.md).

### Command-line examples

```bash
python examples/assess_single_well.py    # single well → JSON / Excel / PDF reports
python examples/screen_portfolio.py      # portfolio screening → ranked table
```

### REST API

```bash
pip install -e ".[api]"
uvicorn lwra.api.main:app --reload
```

| Endpoint | Description |
|---|---|
| `POST /assess` | Assess one well (lean or traced) |
| `POST /assess/batch` | Assess a portfolio in one call |
| `POST /report/{json\|excel\|pdf}` | Assess and download a report |
| `GET /config` | Active weights and thresholds |
| `GET /docs` | Interactive OpenAPI docs |

### Interactive dashboard

```bash
pip install -e ".[dashboard,reports]"
streamlit run src/lwra/dashboard/app.py
```

Open [http://localhost:8501](http://localhost:8501). The sidebar lets you choose
between **sample wells** or **uploading your own data** as a JSON file.
A ready-to-fill template is provided at
[`examples/well_template.json`](examples/well_template.json) — edit the values
and upload via *Single well → Upload JSON*.

---

## Input format

Wells are described as JSON documents conforming to the `WellData` schema.
Key fields:

| Field | Type | Notes |
|---|---|---|
| `well_id` | string | Unique identifier |
| `name` | string | Human-readable name |
| `location` | `{latitude, longitude}` | WGS84 decimal degrees |
| `spud_date` / `abandonment_date` | `YYYY-MM-DD` or `null` | |
| `total_depth_m` | float > 0 | Measured depth in metres |
| `well_type` | enum | `production` · `injection` · `appraisal` · `exploration` · `abandoned` · `unknown` |
| `reservoir_fluid` | enum | `h2s` · `co2` · `gas` · `condensate` · `multiphase` · `oil` · `water` · `unknown` |
| `pressure_bar` / `temperature_c` | float or `null` | |
| `proximity_to_receptors_m` | float or `null` | Distance to nearest sensitive receptor |
| `casing_strings` | array | Name, OD (in), top/bottom depth, cemented flag |
| `barriers` | array | `barrier_type` (`primary`/`secondary`), `element`, depths, `condition_score` (0–1), `verified` |

See [`examples/well_template.json`](examples/well_template.json) for a complete
annotated example.

---

## Tests

```bash
pytest                          # core suite (no optional deps required)
pytest --cov=lwra               # with coverage report
```

CI runs on Python 3.12 and 3.13 with `ruff`, `mypy --strict`, and `pytest`.

---

## Reproducibility & auditability

- Scores are computed from cached, immutable YAML config and rounded to fixed
  precision — results are byte-for-byte reproducible for a given `as_of` date.
- `assess_well_traced` returns the complete derivation tree; the JSON and Excel
  reports can embed it, suiting publication appendices and regulatory archives.

---

## Citation

If you use this tool in research, please cite it using the metadata in
[`CITATION.cff`](CITATION.cff) or via the **Cite this repository** button on
GitHub.

---

## License

MIT — see [`LICENSE`](LICENSE).
Third-party copyright notices and standard references: [`NOTICE.md`](NOTICE.md).
