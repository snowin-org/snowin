"""Plot normalized GUNW phase through xarray's plotting interface."""

from pathlib import Path

import matplotlib.pyplot as plt

from snowin.io import open_gunw

GUNW_FILE = Path("/path/to/NISAR_L2_PR_GUNW_....h5")

with open_gunw(GUNW_FILE, chunks=None) as pair:
    axes = pair["phase"].plot.imshow(
        cmap="twilight",
        robust=True,
        figsize=(9, 6),
        cbar_kwargs={"label": "Normalized phase (rad)"},
    )
    axes.set_title(GUNW_FILE.name)
    plt.show()
