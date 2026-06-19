# References

## Standards and recommended practices

**API RP 90** — *Annular Casing Pressure Management for Offshore Wells.*
American Petroleum Institute, 2nd ed., 2006.
Provides the two-barrier philosophy (primary + independent secondary envelope)
that underpins LWRA's override caps and barrier-role vocabulary.

**NORSOK D-010** — *Well Integrity in Drilling and Well Operations.*
Standards Norway, rev. 4, 2013.
The source of the well-barrier element framework and the principle that every
barrier must be independently verifiable. LWRA's `BarrierElement` taxonomy and
verification-penalty model are informed by this standard.

**ISO 27914:2017** — *Carbon dioxide capture, transportation and geological
storage — Geological storage.*
International Organization for Standardization.
The CO2 storage suitability screening gates in
`recommendation_engine/recommender.py` are inspired by the containment and
well-integrity criteria in this standard. LWRA does not claim conformance.

---

## Technical guidance documents

**IEAGHG (2019).** *Assessment of Sub-surface Risk for CO2 Storage: Well
Integrity.* IEA Greenhouse Gas R&D Programme, Report 2019-03.
Background on well-integrity risk factors relevant to geological CO2 storage.

**Gassnova / Equinor (2012).** *Well Integrity — Lessons Learned.*
Discussion of real-world failure modes that inform LWRA's flag vocabulary and
override rules.

**King, G. E., & King, D. E. (2013).** Environmental risk arising from
well-construction failure — differences between barrier and well failure, and
estimates of failure frequency across common well types, locations, and
well age. *SPE Production & Operations*, 28(04), 323–344.
<https://doi.org/10.2118/166142-PA>
Provides empirical data on well failure rates that informed the default weight
calibration.

**Davies, R. J., et al. (2014).** Oil and gas wells and their integrity:
Implications for shale and unconventional resource exploitation. *Marine and
Petroleum Geology*, 56, 239–254.
<https://doi.org/10.1016/j.marpetgeo.2014.03.001>
Reviews the global evidence base for barrier failure and the significance of
cement integrity.

---

## Software dependencies

| Package | Version constraint | Role |
|---|---|---|
| [Pydantic v2](https://docs.pydantic.dev/) | ≥ 2.6 | Data model validation and serialisation |
| [PyYAML](https://pyyaml.org/) | ≥ 6.0 | YAML configuration loading |
| [Plotly](https://plotly.com/python/) | ≥ 5.20 | Interactive visualisations |
| [ReportLab](https://www.reportlab.com/) | ≥ 4.0 | PDF report generation |
| [OpenPyXL](https://openpyxl.readthedocs.io/) | ≥ 3.1 | Excel report generation |
| [Kaleido](https://github.com/plotly/Kaleido) | latest | Static image export for PDF figures |
| [FastAPI](https://fastapi.tiangolo.com/) | ≥ 0.110 | HTTP API backend |
| [Uvicorn](https://www.uvicorn.org/) | ≥ 0.29 | ASGI server for FastAPI |
| [Streamlit](https://streamlit.io/) | ≥ 1.30 | Interactive dashboard |
| [pytest](https://docs.pytest.org/) | ≥ 8.0 | Test framework |
| [Ruff](https://docs.astral.sh/ruff/) | ≥ 0.4 | Linting and formatting |
| [mypy](https://mypy.readthedocs.io/) | ≥ 1.9 | Static type checking |

---

## Further reading

**Bachu, S. (2008).** CO2 storage in geological media: role, means, status and
barriers to deployment. *Progress in Energy and Combustion Science*, 34(2),
179–197. <https://doi.org/10.1016/j.pecs.2007.10.001>

**Benson, S. M., & Cook, P. (2005).** Underground geological storage.
Chapter 5 in *IPCC Special Report on Carbon Dioxide Capture and Storage.*
Cambridge University Press.

**Thorogood, J. L., & Younger, P. L. (2020).** Chapter 10: Well integrity
for geothermal energy. In *Geothermal Energy: Delivering on the Global
Promise.* Springer.
