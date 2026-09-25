# Reviewer handoff: Ross and Zach

This pull request focuses on SnowIn's reusable scientific API, NISAR GUNW
adapter, scientific tests, and installation/development setup. It does not
include study-specific comparison notebooks or external study data.

## Set up the review environment

From the pull-request branch, create the scientific runtime, add the notebook
and contributor tools, and install the checkout:

```bash
conda env create -f environment.yml
conda activate snowin
conda env update -n snowin -f environment-notebooks.yml
conda env update -n snowin -f environment-dev.yml
python -m pip install -e .
pytest -q
jupyter lab
```

The synthetic notebook runs without external data. To run the real-GUNW
notebook, set local product paths before starting Jupyter:

```bash
export SNOWIN_GUNW=/path/to/NISAR_GUNW.h5
export SNOWIN_NISAR_DEM=/path/to/nisar_modified_cop30.tif
```

The NISAR DEM path is optional when the product's geometry helper can stage it
through its configured cache. No GUNW, DEM, cloud credential, or generated
figure is required by the ordinary test suite.

## Review sequence

1. `notebooks/01_core_snowin_workflow.ipynb` demonstrates the normalized xarray
   contract, dSWE, reference phase, support, temporal accumulation, and metrics
   using synthetic arrays.
2. `notebooks/02_real_nisar_gunw_workflow.ipynb` inspects a caller-supplied
   GUNW, then explicitly adds local-incidence geometry and computes pairwise
   dSWE.
3. Run `pytest -q` for synthetic and regression coverage of the public
   scientific operations, xarray contracts, invalid inputs, and eager/lazy
   behavior. Run optional product checks only when the documented inputs are
   available.

## Scientific review points

- Confirm the normalized phase is `secondary - reference` and dSWE is
  `SWE_secondary - SWE_reference`.
- Check wavelength source, phase transform, coordinate grid, CRS, units, and
  incidence reference in the returned Dataset.
- Confirm missing or unsupported samples remain missing through reference and
  temporal operations.
- For real GUNW data, note geometry support, DEM height reference, runtime,
  memory use, warnings, and any usability issues.

Use [reviewer_feedback_template.md](reviewer_feedback_template.md) to record
the branch/commit, commands, observations, and any reproducible issue.
