"""Quick-look plotting and diagnostics for NISAR GUNW products."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import csv
import json
import platform
import re
import subprocess

import matplotlib.pyplot as plt
from matplotlib import colors as mcolors
import numpy as np
import xarray as xr

from snowin.diagnostics import (
    connected_component_summary,
    mask_summary,
    merge_summaries,
    numeric_summary,
)
from snowin.io.gunw import (
    build_layers,
    detect_grid_epsg,
    detect_pol,
    parse_acquisition_times_from_filename,
    read_attrs_hdf5,
    read_identification_metadata,
)

AMPLITUDE_DB_EPS = 1e-12
@dataclass(frozen=True)
class GunwPlotResult:
    """Paths and summary records produced by ``plot_gunw``."""

    gunw_file: Path
    polarization: str
    figure_paths: tuple[Path, ...]
    summary_csv_path: Path
    metadata_json_path: Path | None
    summary_rows: tuple[dict[str, Any], ...]

    def show(self) -> None:
        """Display generated quick-look figure inline when running in a notebook."""
        for path in self.figure_paths:
            _display_image(path)

    def print_paths(self) -> None:
        """Print generated output paths in a notebook-friendly format."""
        for path in self.figure_paths:
            print(f"figure: {path}")
        print(f"summary_csv: {self.summary_csv_path}")
        if self.metadata_json_path is not None:
            print(f"metadata_json: {self.metadata_json_path}")


def amplitude_to_db(arr: np.ndarray, eps: float = AMPLITUDE_DB_EPS) -> np.ndarray:
    """Convert linear complex amplitude/magnitude to decibels via 20 log10(A)."""
    arr = np.asarray(arr, dtype=float)
    out = np.full(arr.shape, np.nan, dtype=float)
    valid = np.isfinite(arr) & (arr > eps)
    out[valid] = 20.0 * np.log10(arr[valid])
    return out


def dataarray_to_array(
    da: xr.DataArray | None,
    *,
    magnitude: bool = False,
    angle: bool = False,
    db: bool = False,
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    """Convert a GUNW DataArray into a numeric array plus x/y coordinates."""
    if da is None:
        return None, None, None

    arr = da.values
    if getattr(arr.dtype, "fields", None) is not None and {"r", "i"}.issubset(arr.dtype.fields):
        complex_arr = arr["r"] + 1j * arr["i"]
        if magnitude:
            arr = np.abs(complex_arr)
        elif angle:
            arr = np.angle(complex_arr)
        else:
            arr = complex_arr
    elif np.iscomplexobj(arr):
        if magnitude:
            arr = np.abs(arr)
        elif angle:
            arr = np.angle(arr)

    if np.iscomplexobj(arr):
        arr = np.real(arr)

    arr = np.asarray(arr, dtype=float)
    arr[~np.isfinite(arr)] = np.nan
    arr[np.abs(arr) > 1e20] = np.nan

    if db:
        arr = amplitude_to_db(arr)

    y = np.asarray(da.coords[da.dims[0]].values, dtype=float)
    x = np.asarray(da.coords[da.dims[1]].values, dtype=float)
    return arr, x, y


def percentile_limits(arr: np.ndarray, p1: float = 1.0, p99: float = 99.0) -> tuple[float, float]:
    """Return robust display limits from finite array percentiles."""
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return 0.0, 1.0

    vmin, vmax = np.nanpercentile(valid, [p1, p99])
    if not np.isfinite(vmin):
        vmin = np.nanmin(valid)
    if not np.isfinite(vmax):
        vmax = np.nanmax(valid)
    if vmax <= vmin:
        vmax = vmin + 1e-6
    return float(vmin), float(vmax)


def maybe_downsample(
    arr: np.ndarray | None,
    x: np.ndarray | None,
    y: np.ndarray | None,
    max_dim: int = 2200,
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    """Downsample display arrays by simple stride when they are too large."""
    if arr is None or x is None or y is None:
        return arr, x, y
    ny, nx = arr.shape
    step = max(1, int(np.ceil(max(ny, nx) / max_dim)))
    if step == 1:
        return arr, x, y
    return arr[::step, ::step], x[::step], y[::step]


def safe_name_token(value: str) -> str:
    """Return a filename-safe token."""
    token = re.sub(r"[^A-Za-z0-9_\-]+", "_", value.strip())
    token = re.sub(r"_+", "_", token).strip("_")
    return token or "crop"


def basename_no_suffix(path: Path) -> str:
    """Return filename stem while preserving NISAR ``.nc`` stems cleanly."""
    return path.name[:-3] if path.name.endswith(".nc") else path.stem


class GeoJsonCropper:
    """Crop and optionally mask arrays using a GeoJSON geometry."""

    def __init__(self, geom: Any, padding: float = 0.0, mask_outside: bool = True):
        self.geom = geom
        self.padding = float(padding)
        self.mask_outside = bool(mask_outside)
        xmin, ymin, xmax, ymax = self.geom.bounds
        self.bounds = (
            float(xmin - self.padding),
            float(ymin - self.padding),
            float(xmax + self.padding),
            float(ymax + self.padding),
        )

    @classmethod
    def from_geojson(
        cls,
        geojson_file: str | Path,
        target_epsg: int,
        source_epsg: int = 4326,
        padding: float = 0.0,
        mask_outside: bool = True,
    ) -> "GeoJsonCropper":
        """Build a cropper from GeoJSON, reprojecting to the GUNW grid CRS."""
        try:
            from shapely.geometry import shape
            from shapely.ops import transform as shapely_transform
            from shapely.ops import unary_union
        except Exception as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("GeoJSON cropping requires shapely.") from exc

        with Path(geojson_file).open("r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("type") == "FeatureCollection":
            geoms = [shape(feat["geometry"]) for feat in data.get("features", []) if feat.get("geometry")]
            geom = unary_union(geoms)
        elif data.get("type") == "Feature":
            geom = shape(data["geometry"])
        else:
            geom = shape(data)

        if geom.is_empty:
            raise ValueError(f"Crop GeoJSON has no geometry: {geojson_file}")

        if int(source_epsg) != int(target_epsg):
            try:
                from pyproj import Transformer
            except Exception as exc:  # pragma: no cover - dependency guard
                raise RuntimeError("GeoJSON reprojection requires pyproj.") from exc
            transformer = Transformer.from_crs(
                f"EPSG:{int(source_epsg)}",
                f"EPSG:{int(target_epsg)}",
                always_xy=True,
            )
            geom = shapely_transform(transformer.transform, geom)

        return cls(geom=geom, padding=padding, mask_outside=mask_outside)

    def crop_to_bbox(
        self,
        arr: np.ndarray,
        x: np.ndarray,
        y: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Crop array/coords to the crop geometry bounding box."""
        xmin, ymin, xmax, ymax = self.bounds
        x_keep = np.where((x >= xmin) & (x <= xmax))[0]
        y_keep = np.where((y >= ymin) & (y <= ymax))[0]
        if x_keep.size == 0 or y_keep.size == 0:
            return arr[:0, :0], x[:0], y[:0]
        return arr[np.ix_(y_keep, x_keep)], x[x_keep], y[y_keep]

    def mask_array(self, arr: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Mask pixels outside the crop geometry."""
        if not self.mask_outside or arr.size == 0:
            return arr

        xx, yy = np.meshgrid(x, y)
        inside = None

        try:
            import shapely

            if hasattr(shapely, "contains_xy"):
                inside = shapely.contains_xy(self.geom, xx, yy)
        except Exception:
            inside = None

        if inside is None:
            try:
                from shapely import vectorized

                inside = vectorized.contains(self.geom, xx, yy)
            except Exception:
                inside = None

        if inside is None:
            try:
                from rasterio.features import geometry_mask
                from rasterio.transform import Affine
                from shapely.geometry import mapping

                dx = float(np.nanmedian(np.diff(x))) if len(x) > 1 else 1.0
                dy = float(np.nanmedian(np.diff(y))) if len(y) > 1 else -1.0
                transform = Affine(
                    dx,
                    0.0,
                    float(x[0] - dx / 2.0),
                    0.0,
                    dy,
                    float(y[0] - dy / 2.0),
                )
                inside = geometry_mask(
                    [mapping(self.geom)],
                    out_shape=arr.shape,
                    transform=transform,
                    invert=True,
                )
            except Exception as exc:  # pragma: no cover - dependency guard
                raise RuntimeError(
                    "Could not create polygon mask. Install shapely>=2 or rasterio, "
                    "or set mask_outside_geojson=False."
                ) from exc

        out = arr.copy()
        out[~inside] = np.nan
        return out

    def plot_boundary(self, ax: Any, **kwargs: Any) -> None:
        """Overlay crop polygon boundary for visual QC."""
        try:
            geoms = list(self.geom.geoms) if hasattr(self.geom, "geoms") else [self.geom]
            for geom in geoms:
                if hasattr(geom, "exterior") and geom.exterior is not None:
                    xs, ys = geom.exterior.xy
                    ax.plot(xs, ys, **kwargs)
                    for interior in getattr(geom, "interiors", []):
                        xs, ys = interior.xy
                        ax.plot(xs, ys, **kwargs)
                elif hasattr(geom, "xy"):
                    xs, ys = geom.xy
                    ax.plot(xs, ys, **kwargs)
        except Exception:
            return


def _apply_crop(
    arr: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    cropper: GeoJsonCropper | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if cropper is None:
        return arr, x, y
    arr, x, y = cropper.crop_to_bbox(arr, x, y)
    if arr.size == 0:
        return arr, x, y
    return cropper.mask_array(arr, x, y), x, y


def add_horizontal_colorbar(im: Any, ax: Any, label: str | None = None, ticks=None, ticklabels=None):
    """Add a compact horizontal colorbar."""
    cbar = plt.colorbar(im, ax=ax, orientation="horizontal", fraction=0.06, pad=0.08, shrink=0.95)
    if label:
        cbar.set_label(label)
    if ticks is not None:
        cbar.set_ticks(ticks)
    if ticklabels is not None:
        cbar.set_ticklabels(ticklabels)
    cbar.ax.tick_params(labelsize=8)
    return cbar


def discrete_cmap_and_norm(values: np.ndarray, cmap_name: str = "tab20"):
    """Build a discrete colormap/norm for integer QA layers."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return plt.get_cmap(cmap_name).copy(), None, np.array([]), None

    unique_vals = np.unique(finite.astype(np.int64))
    n = len(unique_vals)
    base = plt.get_cmap(cmap_name, max(n, 1))
    cmap = mcolors.ListedColormap(base(np.arange(n)))
    cmap.set_bad(alpha=0.0)

    if n == 1:
        bounds = [unique_vals[0] - 0.5, unique_vals[0] + 0.5]
    else:
        mids = (unique_vals[:-1] + unique_vals[1:]) / 2.0
        first = unique_vals[0] - (mids[0] - unique_vals[0])
        last = unique_vals[-1] + (unique_vals[-1] - mids[-1])
        bounds = np.concatenate([[first], mids, [last]])
    norm = mcolors.BoundaryNorm(bounds, cmap.N)
    ticklabels = [str(int(v)) for v in unique_vals]
    return cmap, norm, unique_vals, ticklabels


def plot_continuous(
    ax: Any,
    da: xr.DataArray | None,
    title: str,
    cmap: str,
    *,
    magnitude: bool = False,
    angle: bool = False,
    db: bool = False,
    max_dim: int = 2200,
    cropper: GeoJsonCropper | None = None,
) -> None:
    """Plot one continuous GUNW layer on an axis."""
    arr, x, y = dataarray_to_array(da, magnitude=magnitude, angle=angle, db=db)
    if arr is None or x is None or y is None:
        ax.set_title(f"{title}\n(not found)", fontsize=10)
        ax.axis("off")
        return

    arr, x, y = _apply_crop(arr, x, y, cropper)
    if arr.size == 0 or np.all(~np.isfinite(arr)):
        ax.set_title(f"{title}\n(no valid cropped data)", fontsize=10)
        ax.axis("off")
        return

    arr, x, y = maybe_downsample(arr, x, y, max_dim=max_dim)
    vmin, vmax = percentile_limits(arr, 1.0, 99.0)
    extent = [float(np.nanmin(x)), float(np.nanmax(x)), float(np.nanmin(y)), float(np.nanmax(y))]
    origin = "upper" if y[0] > y[-1] else "lower"

    cmap_obj = plt.get_cmap(cmap).copy()
    cmap_obj.set_bad(alpha=0.0)
    im = ax.imshow(
        np.ma.masked_invalid(arr),
        extent=extent,
        origin=origin,
        cmap=cmap_obj,
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest",
        aspect="equal",
    )
    if cropper is not None:
        cropper.plot_boundary(ax, color="black", linewidth=0.8, alpha=0.9)

    unit = " dB" if db else ""
    ax.set_title(f"{title}\n[p1={vmin:.3g}{unit}, p99={vmax:.3g}{unit}]", fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    add_horizontal_colorbar(im, ax, label="dB" if db else None)


def plot_discrete(
    ax: Any,
    da: xr.DataArray | None,
    title: str,
    *,
    cmap: str = "tab20",
    max_dim: int = 2200,
    cropper: GeoJsonCropper | None = None,
) -> None:
    """Plot one discrete integer GUNW layer on an axis."""
    arr, x, y = dataarray_to_array(da)
    if arr is None or x is None or y is None:
        ax.set_title(f"{title}\n(not found)", fontsize=10)
        ax.axis("off")
        return

    arr, x, y = _apply_crop(arr, x, y, cropper)
    if arr.size == 0 or np.all(~np.isfinite(arr)):
        ax.set_title(f"{title}\n(no valid cropped data)", fontsize=10)
        ax.axis("off")
        return

    arr, x, y = maybe_downsample(arr, x, y, max_dim=max_dim)
    extent = [float(np.nanmin(x)), float(np.nanmax(x)), float(np.nanmin(y)), float(np.nanmax(y))]
    origin = "upper" if y[0] > y[-1] else "lower"
    cmap_obj, norm, unique_vals, ticklabels = discrete_cmap_and_norm(arr, cmap_name=cmap)
    im = ax.imshow(
        np.ma.masked_invalid(arr),
        extent=extent,
        origin=origin,
        cmap=cmap_obj,
        norm=norm,
        interpolation="nearest",
        aspect="equal",
    )
    if cropper is not None:
        cropper.plot_boundary(ax, color="black", linewidth=0.8, alpha=0.9)
    ax.set_title(title, fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])

    ticks = unique_vals
    labels = ticklabels
    if len(unique_vals) > 12:
        idx = np.unique(np.linspace(0, len(unique_vals) - 1, 12, dtype=int))
        ticks = unique_vals[idx]
        labels = [ticklabels[i] for i in idx]
    add_horizontal_colorbar(im, ax, ticks=ticks, ticklabels=labels)


def _format_dt(dt: datetime | None) -> str:
    return "NA" if dt is None else dt.strftime("%Y-%m-%d %H:%M:%S")


def build_metadata(gunw_file: str | Path, pol: str, crop_geojson: str | Path | None = None) -> dict[str, Any]:
    """Build CSV/JSON-friendly metadata for a GUNW quick-look run."""
    gunw_file = Path(gunw_file)
    meta = read_identification_metadata(gunw_file)
    times = parse_acquisition_times_from_filename(gunw_file)
    out: dict[str, Any] = {
        "gunw_file": str(gunw_file),
        "gunw_name": gunw_file.name,
        "polarization": pol,
        "ref_start": _format_dt(times.ref_start),
        "ref_end": _format_dt(times.ref_end),
        "sec_start": _format_dt(times.sec_start),
        "sec_end": _format_dt(times.sec_end),
        "days_between": times.days_between,
        "crop_geojson": str(crop_geojson) if crop_geojson is not None else None,
    }
    out.update(meta)
    return out


def metadata_text(metadata: dict[str, Any]) -> str:
    """Render compact figure-header metadata."""
    lines = [
        f"Granule: {metadata.get('granuleId', 'NA')}",
        (
            f"Mission: {metadata.get('missionId', 'NA')}   "
            f"Product: {metadata.get('productType', 'NA')}   "
            f"Pol: {metadata.get('polarization', 'NA')}   "
            f"Look: {metadata.get('lookDirection', 'NA')}"
        ),
        (
            f"Track: {metadata.get('trackNumber', 'NA')}   "
            f"Frame: {metadata.get('frameNumber', 'NA')}   "
            f"Ref orbit: {metadata.get('referenceAbsoluteOrbitNumber', 'NA')}   "
            f"Sec orbit: {metadata.get('secondaryAbsoluteOrbitNumber', 'NA')}"
        ),
        (
            f"Ref joint obs: {metadata.get('referenceIsJointObservation', 'NA')}   "
            f"Sec joint obs: {metadata.get('secondaryIsJointObservation', 'NA')}"
        ),
        (
            f"Processing center: {metadata.get('processingCenter', 'NA')}   "
            f"Version: {metadata.get('productVersion', 'NA')}   "
            f"Spec: {metadata.get('productSpecificationVersion', 'NA')}"
        ),
        f"DOI: {metadata.get('productDoi', 'NA')}",
        f"Reference acquisition: {metadata.get('ref_start', 'NA')} to {metadata.get('ref_end', 'NA')}",
        f"Secondary acquisition: {metadata.get('sec_start', 'NA')} to {metadata.get('sec_end', 'NA')}",
        f"Days between acquisition starts: {metadata.get('days_between', 'NA')}",
    ]
    if metadata.get("crop_geojson"):
        lines.append(f"Crop: {Path(str(metadata['crop_geojson'])).name}")
    return "\n".join(lines)


def make_compact_figure(
    layers: dict[str, xr.DataArray | None],
    header_text: str,
    out_png: Path,
    dpi: int,
    max_plot_dim: int,
    cropper: GeoJsonCropper | None = None,
) -> None:
    """Make the standard notebook-friendly pair-screening GUNW figure."""
    fig, axes = plt.subplots(2, 5, figsize=(22, 11))
    axes = axes.ravel()

    plot_continuous(axes[0], layers["unwrapped_phase"], "Unwrapped phase", "viridis", max_dim=max_plot_dim, cropper=cropper)
    plot_continuous(axes[1], layers["wrapped_ifg"], "Wrapped IFG phase", "plasma", angle=True, max_dim=max_plot_dim, cropper=cropper)
    plot_continuous(axes[2], layers["wrapped_ifg"], "Wrapped IFG amplitude (dB)", "cividis", magnitude=True, db=True, max_dim=max_plot_dim, cropper=cropper)
    plot_continuous(axes[3], layers["coherence_unw"], "Coherence (unwrapped)", "plasma", max_dim=max_plot_dim, cropper=cropper)
    plot_discrete(axes[4], layers["connected_components"], "Connected components", cmap="tab20", max_dim=max_plot_dim, cropper=cropper)
    plot_discrete(axes[5], layers["mask"], "Mask", cmap="tab20", max_dim=max_plot_dim, cropper=cropper)
    plot_continuous(axes[6], layers["ionosphere"], "Ionospheric phase screen", "magma", max_dim=max_plot_dim, cropper=cropper)
    plot_continuous(axes[7], layers["ionosphere_unc"], "Ionosphere uncertainty", "cividis", max_dim=max_plot_dim, cropper=cropper)
    plot_continuous(axes[8], layers["corr_peak"], "Correlation surface peak", "viridis", max_dim=max_plot_dim, cropper=cropper)
    plot_continuous(axes[9], layers["wet_tropo"], "Wet tropospheric phase", "magma", max_dim=max_plot_dim, cropper=cropper)

    fig.text(0.5, 0.995, header_text, ha="center", va="top", fontsize=10, family="monospace")
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.83])
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def _attrs_for_row(nc_file: Path, dataset_attr_path: str | None) -> dict[str, Any]:
    if dataset_attr_path is None:
        return {}
    attrs = read_attrs_hdf5(nc_file, dataset_attr_path)
    return {
        "attr_mean_value": attrs.get("mean_value"),
        "attr_min_value": attrs.get("min_value"),
        "attr_max_value": attrs.get("max_value"),
        "attr_sample_stddev": attrs.get("sample_stddev"),
    }


def _summary_array(
    da: xr.DataArray | None,
    *,
    cropper: GeoJsonCropper | None,
    magnitude: bool = False,
    angle: bool = False,
    db: bool = False,
) -> np.ndarray | None:
    arr, x, y = dataarray_to_array(da, magnitude=magnitude, angle=angle, db=db)
    if arr is None or x is None or y is None:
        return None
    arr, _, _ = _apply_crop(arr, x, y, cropper)
    return arr


def build_summary_rows(
    layers: dict[str, xr.DataArray | None],
    dataset_attr_paths: dict[str, str],
    nc_file: str | Path,
    *,
    cropper: GeoJsonCropper | None = None,
) -> list[dict[str, Any]]:
    """Build one CSV row per diagnostic layer/derived layer."""
    nc_file = Path(nc_file)
    specs = [
        ("unwrapped_phase", "unwrapped_phase", "native", False, False, False),
        ("coherence_unw", "coherence_unw", "native", False, False, False),
        ("coherence_wrapped", "coherence_wrapped", "native", False, False, False),
        ("ionosphere", "ionosphere", "native", False, False, False),
        ("ionosphere_unc", "ionosphere_unc", "native", False, False, False),
        ("wrapped_ifg_amplitude", "wrapped_ifg", "magnitude", True, False, False),
        ("wrapped_ifg_amplitude_db", "wrapped_ifg", "magnitude_db", True, False, True),
        ("wrapped_ifg_phase", "wrapped_ifg", "angle", False, True, False),
        ("along_track_offset", "along_track_offset", "native", False, False, False),
        ("slant_range_offset", "slant_range_offset", "native", False, False, False),
        ("corr_peak", "corr_peak", "native", False, False, False),
        ("incidence_angle", "incidence_angle", "native", False, False, False),
        ("parallel_baseline", "parallel_baseline", "native", False, False, False),
        ("perpendicular_baseline", "perpendicular_baseline", "native", False, False, False),
        ("reference_slant_range", "reference_slant_range", "native", False, False, False),
        ("hydro_tropo", "hydro_tropo", "native", False, False, False),
        ("wet_tropo", "wet_tropo", "native", False, False, False),
    ]

    rows: list[dict[str, Any]] = []
    for layer_name, source_name, transform, magnitude, angle, db in specs:
        arr = _summary_array(layers.get(source_name), cropper=cropper, magnitude=magnitude, angle=angle, db=db)
        row = merge_summaries(
            {
                "layer": layer_name,
                "source_layer": source_name,
                "transform": transform,
                "present": arr is not None,
            },
            numeric_summary(arr),
            _attrs_for_row(nc_file, dataset_attr_paths.get(source_name)),
        )
        rows.append(row)

    cc_arr = _summary_array(layers.get("connected_components"), cropper=cropper)
    rows.append(
        merge_summaries(
            {
                "layer": "connected_components",
                "source_layer": "connected_components",
                "transform": "integer_labels",
                "present": cc_arr is not None,
            },
            numeric_summary(cc_arr),
            connected_component_summary(cc_arr),
            _attrs_for_row(nc_file, dataset_attr_paths.get("connected_components")),
        )
    )

    mask_arr = _summary_array(layers.get("mask"), cropper=cropper)
    rows.append(
        merge_summaries(
            {
                "layer": "mask",
                "source_layer": "mask",
                "transform": "qa_mask",
                "present": mask_arr is not None,
            },
            numeric_summary(mask_arr),
            mask_summary(mask_arr),
            _attrs_for_row(nc_file, dataset_attr_paths.get("mask")),
        )
    )
    return rows


def write_summary_csv(rows: list[dict[str, Any]], csv_path: str | Path) -> Path:
    """Write summary rows to CSV with a stable union of columns."""
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def write_metadata_json(metadata: dict[str, Any], json_path: str | Path) -> Path:
    """Write GUNW run metadata JSON."""
    json_path = Path(json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)
    return json_path


def _open_file(path: Path) -> None:
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        elif system == "Linux":
            subprocess.run(["xdg-open", str(path)], check=False)
        elif system == "Windows":
            subprocess.run(["cmd", "/c", "start", "", str(path)], check=False)
    except Exception:
        return


def _display_image(path: Path) -> None:
    """Display a saved PNG inline in a notebook, with a matplotlib fallback."""
    try:
        from IPython.display import Image, display

        display(Image(filename=str(path)))
        return
    except Exception:
        pass

    try:
        img = plt.imread(path)
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.imshow(img)
        ax.axis("off")
        fig.tight_layout()
        plt.show()
    except Exception:
        return


def plot_gunw(
    gunw_file: str | Path,
    *,
    out_dir: str | Path,
    crop_geojson: str | Path | None = None,
    grid_epsg: int | None = None,
    geojson_epsg: int = 4326,
    crop_padding: float = 0.0,
    mask_outside_geojson: bool = True,
    pol: str | None = None,
    radar_cube_index: int = 0,
    dpi: int = 220,
    max_plot_dim: int = 2200,
    write_metadata: bool = True,
    open_plot: bool = False,
    show: bool = False,
    verbose: bool = False,
) -> GunwPlotResult:
    """Create GUNW quick-look figure(s) and a CSV diagnostic summary.

    Parameters
    ----------
    gunw_file
        Path to a NISAR GUNW ``.nc`` product.
    out_dir
        Output directory for figure(s), summary CSV, and metadata JSON.
    crop_geojson
        Optional AOI polygon. When supplied, figure panels and CSV summaries are
        cropped to the polygon bounding box and masked outside the polygon by
        default.
    grid_epsg
        EPSG code of the GUNW x/y grid. Auto-detected when possible.
    geojson_epsg
        EPSG code for the input GeoJSON coordinates.
    crop_padding
        Padding around the crop GeoJSON bounds in grid units, usually meters.
    mask_outside_geojson
        If ``True``, mask pixels outside the polygon. If ``False``, crop only to
        the polygon bounding box.
    pol
        Optional polarization override. If omitted, HH then VV are detected.
    radar_cube_index
        Height index for radar-grid 3-D metadata layers.
    write_metadata
        Write metadata JSON alongside the summary CSV.
    open_plot
        Open the generated figure with the operating system default viewer.
    show
        Display the generated quick-look figure inline when running in a notebook.
    verbose
        Print generated output paths.

    Returns
    -------
    GunwPlotResult
        Paths and in-memory summary rows.
    """
    gunw_file = Path(gunw_file).expanduser().resolve()
    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not gunw_file.exists():
        raise FileNotFoundError(f"GUNW file not found: {gunw_file}")
    pol_resolved = pol or detect_pol(gunw_file)

    cropper = None
    crop_name_suffix = ""
    if crop_geojson is not None:
        crop_geojson = Path(crop_geojson).expanduser().resolve()
        if not crop_geojson.exists():
            raise FileNotFoundError(f"Crop GeoJSON file not found: {crop_geojson}")
        grid_epsg_resolved = grid_epsg or detect_grid_epsg(gunw_file)
        if grid_epsg_resolved is None:
            raise ValueError("Could not auto-detect GUNW grid EPSG. Pass grid_epsg explicitly.")
        cropper = GeoJsonCropper.from_geojson(
            crop_geojson,
            target_epsg=grid_epsg_resolved,
            source_epsg=geojson_epsg,
            padding=crop_padding,
            mask_outside=mask_outside_geojson,
        )
        crop_name_suffix = f"_{safe_name_token(crop_geojson.stem)}"

    layers, dataset_attr_paths = build_layers(gunw_file, pol_resolved, radar_cube_index)
    metadata = build_metadata(gunw_file, pol_resolved, crop_geojson)
    header = metadata_text(metadata)

    stem = f"{basename_no_suffix(gunw_file)}_{pol_resolved}{crop_name_suffix}"
    figure_paths: list[Path] = []

    out_png = out_dir / f"{stem}_quickview.png"
    make_compact_figure(layers, header, out_png, dpi, max_plot_dim, cropper=cropper)
    figure_paths.append(out_png)

    rows = build_summary_rows(layers, dataset_attr_paths, gunw_file, cropper=cropper)
    summary_csv = write_summary_csv(rows, out_dir / f"{stem}_summary_stats.csv")

    metadata_path: Path | None = None
    if write_metadata:
        metadata_path = write_metadata_json(metadata, out_dir / f"{stem}_metadata.json")

    result = GunwPlotResult(
        gunw_file=gunw_file,
        polarization=pol_resolved,
        figure_paths=tuple(figure_paths),
        summary_csv_path=summary_csv,
        metadata_json_path=metadata_path,
        summary_rows=tuple(rows),
    )

    if open_plot:
        for path in result.figure_paths:
            _open_file(path)
    if show:
        result.show()
    if verbose:
        result.print_paths()

    return result
