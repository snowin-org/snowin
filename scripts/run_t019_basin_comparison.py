"""Run the real 23-edge Colorado basin-aware SnowIn comparison.

This is an intentionally explicit validation script rather than a package API.
It consumes the local Colorado path manifest and downstream rasters, then
compares controlled (Colorado incidence/frozen wavelength) and native
(SnowIn NISAR DEM/product wavelength) results inside the ERB and Taylor masks.
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import numpy as np
import rasterio
import xarray as xr

from scripts.study_utils.spatial import rasterize_vector_mask
from snowin import accumulate_dswe, compute_dswe, reference_phase
from snowin.io import add_gunw_incidence, open_gunw

DEFAULT_DATA_DIR = Path.home() / ".cache" / "snowin" / "colorado"
MANIFEST = Path(
    os.environ.get(
        "SNOWIN_COLORADO_MANIFEST", DEFAULT_DATA_DIR / "t019_path_manifest.json"
    )
)
DEM = Path(os.environ.get("SNOWIN_NISAR_DEM", DEFAULT_DATA_DIR / "nisar_cop30.tif"))
ERB_VECTOR = Path(os.environ.get("SNOWIN_ERB_VECTOR", DEFAULT_DATA_DIR / "erb.gpkg"))
TAYLOR_VECTOR = Path(
    os.environ.get("SNOWIN_TAYLOR_VECTOR", DEFAULT_DATA_DIR / "taylor.gpkg")
)
ERB_LAYER = os.environ.get("SNOWIN_ERB_LAYER", "erb")
TAYLOR_LAYER = os.environ.get(
    "SNOWIN_TAYLOR_LAYER", "taylor_river_below_taylor_park_reservoir_nldi_basin"
)
DOWNSTREAM_DIR = Path(
    os.environ.get(
        "SNOWIN_COLORADO_DOWNSTREAM_DIR", DEFAULT_DATA_DIR / "downstream-path"
    )
)
REPORT = Path(
    os.environ.get(
        "SNOWIN_COLORADO_REPORT", DEFAULT_DATA_DIR / "t019_basin_full_comparison.json"
    )
)
FROZEN_WAVELENGTH_M = 0.238403545
REGIONS = {
    "east_river": (ERB_VECTOR, ERB_LAYER),
    "taylor": (TAYLOR_VECTOR, TAYLOR_LAYER),
}


def _finite_fraction(values: np.ndarray, region: np.ndarray) -> float:
    count = int(region.sum())
    return float(np.isfinite(values[region]).sum() / count) if count else float("nan")


def _stats(
    left: np.ndarray, right: np.ndarray, mask: np.ndarray
) -> dict[str, float | int]:
    valid = mask & np.isfinite(left) & np.isfinite(right)
    x = left[valid].astype(float)
    y = right[valid].astype(float)
    if x.size == 0:
        return {"count": 0}
    difference = x - y
    x_centered = x - x.mean()
    y_centered = y - y.mean()
    denominator = np.sqrt(
        np.dot(x_centered, x_centered) * np.dot(y_centered, y_centered)
    )
    return {
        "count": int(x.size),
        "bias_left_minus_right": float(difference.mean()),
        "mae": float(np.abs(difference).mean()),
        "rmse": float(np.sqrt(np.mean(difference**2))),
        "p95_abs_error": float(np.percentile(np.abs(difference), 95)),
        "max_abs_error": float(np.abs(difference).max()),
        "pearson_r": float(np.dot(x_centered, y_centered) / denominator)
        if denominator
        else float("nan"),
        "left_mean": float(x.mean()),
        "right_mean": float(y.mean()),
    }


def _downstream_array(path: Path, shape: tuple[int, int]) -> np.ndarray:
    with rasterio.open(path) as source:
        values = source.read(1).astype(float)
        nodata = source.nodata
    if values.shape != shape:
        raise ValueError(f"{path} has shape {values.shape}; expected {shape}")
    if nodata is not None:
        values[values == nodata] = np.nan
    return values


def _cropped_edge(
    values: np.ndarray,
    support: np.ndarray,
    region: np.ndarray,
    y: xr.DataArray,
    x: xr.DataArray,
    attrs: dict[str, object],
) -> xr.Dataset:
    y_slice, x_slice = _region_slices(region)
    cropped_region = region[y_slice, x_slice]
    dswe = xr.DataArray(
        values[y_slice, x_slice],
        dims=("y", "x"),
        coords={"y": y.isel(y=y_slice), "x": x.isel(x=x_slice)},
        name="dswe",
        attrs={
            "units": "m",
            "quantity": "pairwise_dSWE",
            "phase_difference_definition": "secondary_minus_reference",
        },
    ).where(cropped_region)
    declared_support = xr.DataArray(
        support[y_slice, x_slice] & cropped_region,
        dims=("y", "x"),
        coords={"y": y.isel(y=y_slice), "x": x.isel(x=x_slice)},
        name="pairwise_supported",
    )
    return xr.Dataset(
        {"dswe": dswe, "pairwise_supported": declared_support},
        attrs={
            **attrs,
            "temporal_edge": "reference_to_secondary",
        },
    )


def _region_slices(region: np.ndarray) -> tuple[slice, slice]:
    rows, columns = np.where(region)
    if rows.size == 0:
        raise ValueError("analysis region has no pixels")
    return slice(rows.min(), rows.max() + 1), slice(columns.min(), columns.max() + 1)


def _read_controlled_incidence(path: Path, shape: tuple[int, int]) -> np.ndarray:
    with rasterio.open(path) as source:
        values = source.read(1).astype(float)
    if values.shape != shape:
        raise ValueError(f"{path} has shape {values.shape}; expected {shape}")
    return np.where((values >= 0.0) & (values < 90.0), np.deg2rad(values), np.nan)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    edges = manifest["edges"]
    if len(edges) != 23:
        raise ValueError(f"expected 23 Colorado edges, found {len(edges)}")

    print(f"[snowin] loading {len(edges)} Colorado edges from {MANIFEST}")
    first = open_gunw(
        Path(edges[0]["product_path"]),
        wavelength_m=FROZEN_WAVELENGTH_M,
        chunks=None,
        progress=False,
    )
    try:
        shape = (first.sizes["y"], first.sizes["x"])
        controlled_incidence = _read_controlled_incidence(
            Path(edges[0]["incidence_path"]), shape
        )
        regions = {
            name: rasterize_vector_mask(
                path, target=first, layer=layer, progress=False
            ).values.astype(bool)
            for name, (path, layer) in REGIONS.items()
        }
        coordinates = (first["y"], first["x"])
    finally:
        first.close()

    regional_edges: dict[str, dict[str, list[xr.Dataset]]] = {
        name: {"controlled": [], "native_product": [], "native_frozen": []}
        for name in REGIONS
    }
    edge_results: list[dict[str, object]] = []
    started = time.perf_counter()

    for index, item in enumerate(edges, start=1):
        edge_started = time.perf_counter()
        product = Path(item["product_path"])
        raw_offset = float(item["offset_rad"])
        print(f"[snowin] edge {index:02d}/23: {product.name}")

        controlled = open_gunw(
            product, wavelength_m=FROZEN_WAVELENGTH_M, chunks=None, progress=False
        )
        try:
            controlled["incidence_angle"] = (
                controlled["phase"]
                .copy(data=controlled_incidence)
                .rename("incidence_angle")
            )
            controlled["incidence_angle"].attrs = {
                "units": "rad",
                "incidence_angle_reference": "local",
                "source": "Colorado incidence raster",
            }
            controlled = reference_phase(
                controlled, method="manual_offset", offset_rad=-raw_offset
            )
            controlled_dswe = compute_dswe(
                controlled["phase_referenced"],
                controlled["incidence_angle"],
                wavelength_m=FROZEN_WAVELENGTH_M,
            ).values
            time_attrs = {
                "reference_time": controlled.attrs["reference_time"],
                "secondary_time": controlled.attrs["secondary_time"],
            }
            controlled_incidence_values = controlled["incidence_angle"].values

            native = open_gunw(product, chunks=None, progress=False)
            try:
                add_gunw_incidence(
                    native,
                    product,
                    dem_source="nisar_cop30",
                    dem=DEM,
                    progress=False,
                )
                native = reference_phase(
                    native, method="manual_offset", offset_rad=-raw_offset
                )
                native_angle = native["incidence_angle"].where(
                    (native["incidence_angle"] >= 0.0)
                    & (native["incidence_angle"] < math.pi / 2.0)
                )
                native_product_dswe = compute_dswe(
                    native["phase_referenced"],
                    native_angle,
                    wavelength_m=float(native.attrs["wavelength_m"]),
                ).values
                native_frozen_dswe = compute_dswe(
                    native["phase_referenced"],
                    native_angle,
                    wavelength_m=FROZEN_WAVELENGTH_M,
                ).values
                native_angle_values = native_angle.values
                native_wavelength = float(native.attrs["wavelength_m"])

                edge_result: dict[str, object] = {
                    "index": index,
                    "pair_id": item["pair_id"],
                    "reference_date": item["reference_date"],
                    "secondary_date": item["secondary_date"],
                    "product_path": str(product),
                    "raw_offset_rad": raw_offset,
                    "snowin_reference_offset_rad": -raw_offset,
                    "native_wavelength_m": native_wavelength,
                    "runtime_s": time.perf_counter() - edge_started,
                    "regions": {},
                }
                for region_name, region in regions.items():
                    angle_mask = (
                        region
                        & np.isfinite(controlled_incidence_values)
                        & np.isfinite(native_angle_values)
                    )
                    native_support = np.isfinite(native_product_dswe)
                    frozen_support = np.isfinite(native_frozen_dswe)
                    controlled_support = np.isfinite(controlled_dswe)
                    downstream = _downstream_array(
                        DOWNSTREAM_DIR / f"pair_{index:03d}_dswe_mm.tif", shape
                    )
                    downstream_common = region & np.isfinite(downstream)
                    # Colorado's downstream output uses the opposite sign of
                    # SnowIn's canonical dSWE, so equality is tested by sum.
                    downstream_residual_mask = (
                        downstream_common & controlled_support & native_support
                    )
                    edge_result["regions"][region_name] = {
                        "region_pixels": int(region.sum()),
                        "region_fraction_full_grid": float(region.mean()),
                        "incidence_common_valid_fraction": float(
                            angle_mask.sum() / region.sum()
                        ),
                        "incidence_native_minus_controlled_deg": _stats(
                            np.rad2deg(native_angle_values),
                            np.rad2deg(controlled_incidence_values),
                            angle_mask,
                        ),
                        "controlled_dswe_support_fraction": _finite_fraction(
                            controlled_dswe, region
                        ),
                        "native_product_dswe_support_fraction": _finite_fraction(
                            native_product_dswe, region
                        ),
                        "native_frozen_dswe_support_fraction": _finite_fraction(
                            native_frozen_dswe, region
                        ),
                        "native_product_minus_controlled_dswe_mm": _stats(
                            native_product_dswe * 1000.0,
                            controlled_dswe * 1000.0,
                            region,
                        ),
                        "native_frozen_minus_controlled_dswe_mm": _stats(
                            native_frozen_dswe * 1000.0,
                            controlled_dswe * 1000.0,
                            region,
                        ),
                        "controlled_plus_downstream_dswe_mm": _stats(
                            controlled_dswe * 1000.0,
                            -downstream,
                            downstream_residual_mask,
                        ),
                        "native_product_plus_downstream_dswe_mm": _stats(
                            native_product_dswe * 1000.0,
                            -downstream,
                            downstream_residual_mask,
                        ),
                    }
                    for mode, values, support in (
                        ("controlled", controlled_dswe, controlled_support),
                        ("native_product", native_product_dswe, native_support),
                        ("native_frozen", native_frozen_dswe, frozen_support),
                    ):
                        regional_edges[region_name][mode].append(
                            _cropped_edge(
                                values,
                                support,
                                region,
                                coordinates[0],
                                coordinates[1],
                                time_attrs,
                            )
                        )
                edge_results.append(edge_result)
                print(
                    f"[snowin] edge {index:02d}/23 complete in "
                    f"{edge_result['runtime_s']:.1f}s"
                )
            finally:
                native.close()
        finally:
            controlled.close()

    accumulations: dict[str, object] = {}
    downstream_cumulative = _downstream_array(
        DOWNSTREAM_DIR / "cumulative_dswe_mm.tif", shape
    )
    for region_name, modes in regional_edges.items():
        region = regions[region_name]
        region_results: dict[str, object] = {}
        y_slice, x_slice = _region_slices(region)
        downstream_region = downstream_cumulative[y_slice, x_slice]
        for mode, edge_list in modes.items():
            accumulated = accumulate_dswe(edge_list)
            final = accumulated["cumulative_dswe"].isel(time=-1).values
            support = accumulated["temporal_path_supported"].isel(time=-1).values
            region_crop = region[y_slice, x_slice]
            final_supported = np.isfinite(final) & region_crop
            path_supported = support.astype(bool) & region_crop
            region_results[mode] = {
                "final_support_fraction_of_region": float(
                    final_supported.sum() / region.sum()
                ),
                "final_path_support_fraction_of_region": float(
                    path_supported.sum() / region.sum()
                ),
                "final_vs_downstream_mm": _stats(
                    final * 1000.0,
                    -downstream_region,
                    np.isfinite(final) & np.isfinite(downstream_region),
                ),
                "edge_count": int(accumulated.attrs["temporal_edge_count"]),
                "final_supported_pixels": int(final_supported.sum()),
                "final_path_supported_pixels": int(path_supported.sum()),
            }
        accumulations[region_name] = region_results

    report = {
        "manifest": str(MANIFEST),
        "dem": str(DEM),
        "downstream_dir": str(DOWNSTREAM_DIR),
        "frozen_wavelength_m": FROZEN_WAVELENGTH_M,
        "regions": {
            name: {
                "vector": str(REGIONS[name][0]),
                "layer": REGIONS[name][1],
                "pixels": int(regions[name].sum()),
                "fraction_full_grid": float(regions[name].mean()),
            }
            for name in REGIONS
        },
        "edge_count": len(edge_results),
        "total_runtime_s": time.perf_counter() - started,
        "edges": edge_results,
        "accumulations": accumulations,
        "interpretation": {
            "downstream_sign_rule": "SnowIn + downstream = residual; downstream is opposite sign",
            "native_mode": "NISAR-modified Copernicus DEM with product-derived wavelength",
            "controlled_mode": "Colorado incidence raster with frozen wavelength",
            "native_frozen_mode": "SnowIn NISAR DEM geometry with frozen wavelength",
        },
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2))
    print(f"[snowin] wrote {REPORT}")
    print(f"[snowin] total runtime {report['total_runtime_s']:.1f}s")


if __name__ == "__main__":
    main()
