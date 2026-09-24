# Independent NIVAL 20 m unwrap and SnowIn result

This run used the operational NISAR L2 GUNW and the two public NIVAL snow-depth
rasters for Mores Creek Summit, Idaho. The source data were staged under
`/private/tmp/snowin_nival_nisar`; the 2.3 GB GUNW and lidar inputs are not in
the Git branch. The GUNW and lidar files were downloaded from ASF and NSIDC
with the existing Earthdata `.netrc` login. No raw RSLC granules were needed.

ISCE3 0.25.12 was already installed in the local `isce3` conda environment.
The unwrap script reads the GUNW's delivered 20 m complex
`wrappedInterferogram` and coherence, crops the Mores AOI, and calls ISCE3's
ICU algorithm directly. It does not call Zach's code or rerun GUNW formation.
The output preserves the source GUNW phase orientation. For the SnowIn step,
`scripts/derive_unwrapped_gunw_dswe.py` normalizes phase to
`secondary_minus_reference`, uses SnowIn's local-incidence calculation and
dSWE kernel, and saves both canonical SnowIn dSWE and a sign-adjusted
reference-comparison field.

The paper's main 80 m comparison was also run through SnowIn and then plotted
with Zach's unchanged `nival.paper_figures.results_figure()` function. The
sign adjustment is needed because Zach applies the positive Leinss conversion
to source-orientation GUNW phase, while SnowIn uses canonical
`secondary_minus_reference` phase.

## Results

| GUNW layer / coherence gate | valid pairs | r | centered RMSD | fitted density |
|---|---:|---:|---:|---:|
| 80 m, all | 4,976 | 0.817 | 19.0 mm | 143.4 kg/m³ |
| 80 m, > 0.2 | 2,891 | 0.928 | 12.0 mm | 156.4 kg/m³ |
| 80 m, > 0.3 | 1,843 | 0.949 | 10.4 mm | 158.7 kg/m³ |
| 80 m, > 0.4 | 1,004 | 0.962 | 9.5 mm | 162.1 kg/m³ |
| 80 m, > 0.5 | 463 | 0.959 | 9.7 mm | 163.2 kg/m³ |
| 20 m ISCE3 ICU, all | 77,178 | 0.717 | 23.3 mm | 122.6 kg/m³ |
| 20 m ISCE3 ICU, > 0.2 | 62,647 | 0.761 | 21.6 mm | 131.1 kg/m³ |
| 20 m ISCE3 ICU, > 0.3 | 39,253 | 0.838 | 18.1 mm | 145.0 kg/m³ |
| 20 m ISCE3 ICU, > 0.4 | 22,486 | 0.896 | 14.9 mm | 154.4 kg/m³ |
| 20 m ISCE3 ICU, > 0.5 | 12,096 | 0.921 | 13.3 mm | 158.5 kg/m³ |

The 80 m pixel counts, correlations, and rounded centered RMSD reproduce the
reference repository's headline values. Fitted density differs modestly from
the repository README values, consistent with the notebook's noted
wavelength/geometry implementation differences. The paper reports 20 m
correlation r=0.75 for its SNAPHU result; the independent ISCE3 ICU result here
is r=0.717. ICU is a different unwrapping algorithm, so the 20 m output is a
cross-check rather than an exact reproduction of Figure 3.

The independent ICU crop is 510 columns by 536 rows at 20 m. It has 273,360
valid unwrapped pixels, four component labels including unassigned label 0,
and 83.3% of valid pixels in the largest component.
Artifacts from this run are in the ignored `outputs/nival_nisar/` directory;
`fig2_results.png` was rendered by Zach's unchanged plotting function from the
SnowIn-compatible 80 m NetCDF.

## Reproduce

Download the GUNW, lidar and one local DEM tile (the DEM download does not
require Earthdata):

```bash
python scripts/download_nival_nisar_inputs.py --inputs all --interactive-login
```

Run the independent ISCE3 ICU unwrap and SnowIn dSWE handoff:

```bash
conda run -n isce3 python scripts/unwrap_gunw_20m_isce3.py \
  ~/.cache/snowin/nival_nisar/gunw/NISAR_L2_PR_GUNW_012_077_A_024_013_4000_SH_20260207T124619_20260207T124654_20260219T124619_20260219T124654_P05023_N_F_J_001.h5 \
  --output outputs/nival_nisar/isce3_icu_20m_unwrapped.tif

conda run -n nisar_snotel python scripts/derive_unwrapped_gunw_dswe.py \
  --gunw ~/.cache/snowin/nival_nisar/gunw/NISAR_L2_PR_GUNW_012_077_A_024_013_4000_SH_20260207T124619_20260207T124654_20260219T124619_20260219T124654_P05023_N_F_J_001.h5 \
  --phase outputs/nival_nisar/isce3_icu_20m_unwrapped.tif \
  --output outputs/nival_nisar/snowin_20m_dswe.nc \
  --cop30-dem ~/.cache/snowin/nival_nisar/dem/Copernicus_DSM_COG_10_N43_00_W116_00_DEM.tif
```

The 80 m SnowIn workflow and optional handoff to Zach's Figure 2 plot are
documented in [notebook 05](../notebooks/05_nival_nisar_comparison.ipynb).
