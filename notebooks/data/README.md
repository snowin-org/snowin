# Bundled GUNW notebook sample

`nisar_sample_gunw_crop.h5` is a small spatial crop of the official ASF NISAR
sample product:

`NISAR_L2_PR_GUNW_001_030_A_019_002_2000_SH_20081012T060911_20081012T060925_20081127T061000_20081127T061014_D00404_N_F_J_001.h5`

The original sample product is available from [ASF's public NISAR
sample-data bucket][sample-product]. ASF describes [the sample data][sample-guide]
as material for learning the product format and developing workflows. This is a
prelaunch sample, not a production NISAR acquisition or a snow-science
validation scene.

The fixture keeps the centered 128 × 128 unwrapped-phase crop, its matching
wrapped and pixel-offset grids, a 20 × 22 × 22 radar-grid lookup subset, and the
source metadata needed by `open_gunw()` and `add_gunw_incidence()`. The crop is
3,822,054 bytes. It demonstrates adapter and notebook execution only; its
computed dSWE is not a scientific estimate.

The original download was 264,241,152 bytes (SHA-256
`78703c13bd7aafaf5520dbe098c5e1b6f2dec96cc6c12a12c8930091e7531c98`). The
phase crop uses zero-based rows `713:841` and columns `504:632` from its
unwrapped grid.

SHA-256 of the crop:

```text
8acfe81edd9b36f9df0d5e624b7a163a30a473e6acf5d6aec490722c9b833dcd
```

[sample-product]: https://nisar.asf.earthdatacloud.nasa.gov/NISAR-SAMPLE-DATA/GUNW/NISAR_L2_PR_GUNW_001_030_A_019_002_2000_SH_20081012T060911_20081012T060925_20081127T061000_20081127T061014_D00404_N_F_J_001/NISAR_L2_PR_GUNW_001_030_A_019_002_2000_SH_20081012T060911_20081012T060925_20081127T061000_20081127T061014_D00404_N_F_J_001.h5
[sample-guide]: https://asf.alaska.edu/working-with-nisar-sample-data/
