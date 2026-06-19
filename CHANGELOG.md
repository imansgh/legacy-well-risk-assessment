# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2024-01-01

### Added

**Core engines**
- `integrity_engine`: scores five barrier components (primary barrier, secondary
  barrier, cement quality, mechanical integrity, plugging) and aggregates them
  into an overall 0-100 integrity score with well-barrier-philosophy hard caps.
- `risk_engine`: normalises seven risk factors (integrity score, well age,
  reservoir pressure, temperature, fluid hazard, proximity to receptors, data
  uncertainty) and produces a scalar risk score plus a 5×5 risk-matrix
  (likelihood × consequence) placement.
- `recommendation_engine`: gate-based CO2-storage and geothermal suitability
  screening (ISO 27914-inspired), engineering verdict (reuse / remediate /
  monitor / abandon), required actions, and confidence score.

**Pipeline**
- `services.pipeline.assess_well` — lean `WellAssessment` aggregate (for
  dashboards and ML feature rows).
- `services.pipeline.assess_well_traced` — same object with full
  `calculation_trace` for audit, reports, and publications.

**Visualisations** (Plotly)
- Integrity and risk score gauges.
- Five-component radar chart.
- 5×5 risk-matrix heatmap with well placement.
- Weighted risk-contribution and portfolio comparison bar charts.

**Reports**
- PDF report (ReportLab) — title block, score summary, embedded figures,
  recommendations, and optional calculation trace.
- Excel workbook (OpenPyXL) — inputs, component scores, risk factors, and
  full audit trail across multiple sheets.
- JSON report — lean or fully traced, suitable for API responses and
  database archiving.

**API**
- FastAPI backend: `GET /health`, `GET /config`, `POST /assess`,
  `POST /assess/batch`, `POST /report/{json|excel|pdf}`.

**Dashboard**
- Streamlit interactive dashboard with well picker, live assessment,
  all four visualisations, and report download buttons.

**Data model**
- Pydantic v2 frozen models: `WellData`, `BarrierData`, `CasingString`,
  `GeoLocation`, `IntegrityResult`, `RiskResult`, `RecommendationResult`,
  `WellAssessment`.
- All weights and thresholds externalised to `weights.yaml` /
  `thresholds.yaml` — tunable without code changes.

**Developer tooling**
- `pytest` test suite with deterministic fixtures.
- `ruff` linting and `mypy` strict type checking.
- `hatchling` build backend with optional dependency groups
  (`viz`, `reports`, `api`, `dashboard`, `dev`, `all`).
- Example scripts: single-well assessment and portfolio batch screening.

[0.1.0]: https://github.com/lwra-project/lwra/releases/tag/v0.1.0
