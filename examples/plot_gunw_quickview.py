"""Example: make GUNW quick-look plots and diagnostic CSVs with SnowIn."""

from pathlib import Path

from snowin import plot_gunw

GUNW_FILE = Path("/path/to/NISAR_L2_PR_GUNW_....nc")
OUT_DIR = Path("plots/gunw_quicklooks")
CROP_GEOJSON = Path("/path/to/basin.geojson")  # or None

result = plot_gunw(
    GUNW_FILE,
    out_dir=OUT_DIR,
    crop_geojson=CROP_GEOJSON,
    grid_epsg=None,  # auto-detect when possible; pass 32611/32613/etc if needed
    show=True,  # display inline in Jupyter notebooks
    verbose=True,
)
