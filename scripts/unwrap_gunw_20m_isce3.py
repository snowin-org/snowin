"""Unwrap the delivered NISAR GUNW 20 m wrapped interferogram with ISCE3 ICU.

This is an independent, optional diagnostic for the NIVAL pair. It reads only
the wrapped interferogram and coherence already in the operational GUNW; it
does not form an interferogram from RSLCs. The output phase keeps the source
GUNW orientation (reference minus secondary). ISCE3's ICU algorithm is used
here instead of Zach Hoppinen's SNAPHU run, so it is a separate unwrap, not an
exact reproduction of his 20 m figure.

Run in an environment with ISCE3 and GDAL, for example:

    conda run -n isce3 python scripts/unwrap_gunw_20m_isce3.py \
      /path/to/NISAR_L2_PR_GUNW_...h5 \
      --output /path/to/nival_20m_isce3_icu.tif

The default AOI is Zach's Mores Creek box. Pass --aoi west south east north
in EPSG:4326 to select another subset. Results are a phase GeoTIFF and a
connected-components GeoTIFF beside it.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import h5py
import isce3
import numpy as np
from osgeo import gdal, osr

WRAPPED_GROUP = "science/LSAR/GUNW/grids/frequencyA/wrappedInterferogram/HH"
DEFAULT_AOI = (-115.745, 43.898, -115.620, 43.993)


def _window(group: h5py.Group, aoi: tuple[float, float, float, float]):
    """Return a contiguous y/x crop for an EPSG:4326 box."""
    projection = group["projection"].attrs
    epsg = int(projection["epsg_code"])
    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)
    source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    target = osr.SpatialReference()
    target.ImportFromEPSG(epsg)
    transform = osr.CoordinateTransformation(source, target)
    west, south, east, north = aoi
    corners = [
        transform.TransformPoint(lon, lat)
        for lon, lat in (
            (west, south),
            (west, north),
            (east, south),
            (east, north),
        )
    ]
    xs = np.asarray(group["xCoordinates"][:], dtype=np.float64)
    ys = np.asarray(group["yCoordinates"][:], dtype=np.float64)
    x_min, x_max = (
        min(point[0] for point in corners),
        max(point[0] for point in corners),
    )
    y_min, y_max = (
        min(point[1] for point in corners),
        max(point[1] for point in corners),
    )
    cols = np.flatnonzero((xs >= x_min) & (xs <= x_max))
    rows = np.flatnonzero((ys >= y_min) & (ys <= y_max))
    if not cols.size or not rows.size:
        raise ValueError(f"AOI does not intersect the GUNW grid: {aoi}")
    return epsg, xs, ys, slice(rows[0], rows[-1] + 1), slice(cols[0], cols[-1] + 1)


def _write_raster(
    path: Path,
    values: np.ndarray,
    *,
    epsg: int,
    x0_center: float,
    y0_center: float,
    dx: float,
    dy: float,
    data_type: int,
    nodata: float | None = None,
    metadata: dict[str, str] | None = None,
) -> None:
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(
        str(path),
        int(values.shape[1]),
        int(values.shape[0]),
        1,
        data_type,
        options=["TILED=YES", "COMPRESS=DEFLATE"],
    )
    if dataset is None:
        raise RuntimeError(f"Could not create GeoTIFF: {path}")
    spatial_ref = osr.SpatialReference()
    spatial_ref.ImportFromEPSG(epsg)
    dataset.SetProjection(spatial_ref.ExportToWkt())
    dataset.SetGeoTransform(
        (x0_center - dx / 2.0, dx, 0.0, y0_center - dy / 2.0, 0.0, dy)
    )
    if metadata:
        dataset.SetMetadata(metadata)
    band = dataset.GetRasterBand(1)
    band.WriteArray(values)
    if nodata is not None:
        band.SetNoDataValue(nodata)
    band.FlushCache()
    dataset.FlushCache()
    dataset = None


def unwrap_gunw_20m(
    gunw_path: Path,
    output_path: Path,
    *,
    aoi: tuple[float, float, float, float] = DEFAULT_AOI,
) -> tuple[Path, Path]:
    """Run ISCE3 ICU on a crop of the GUNW's delivered 20 m wrapped layer."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conncomp_path = output_path.with_name(
        f"{output_path.stem}_connected_components{output_path.suffix}"
    )

    with h5py.File(gunw_path, "r") as source:
        group = source[WRAPPED_GROUP]
        epsg, xs, ys, row_slice, col_slice = _window(group, aoi)
        igram = np.asarray(
            group["wrappedInterferogram"][row_slice, col_slice], dtype=np.complex64
        )
        coherence = np.asarray(
            group["coherenceMagnitude"][row_slice, col_slice], dtype=np.float32
        )
        x_crop = xs[col_slice]
        y_crop = ys[row_slice]

    if x_crop.size < 2 or y_crop.size < 2:
        raise ValueError("The selected AOI must contain at least two rows and columns")
    dx = float(x_crop[1] - x_crop[0])
    dy = float(y_crop[1] - y_crop[0])
    if not np.allclose(np.diff(x_crop), dx) or not np.allclose(np.diff(y_crop), dy):
        raise ValueError("GUNW x/y coordinates must be regularly spaced")

    valid = (
        np.isfinite(igram.real)
        & np.isfinite(igram.imag)
        & ((igram.real != 0.0) | (igram.imag != 0.0))
        & np.isfinite(coherence)
    )
    if not valid.any():
        raise ValueError("The selected GUNW crop contains no valid wrapped pixels")
    igram[~valid] = 0.0 + 0.0j
    coherence[~valid] = 0.0

    with tempfile.TemporaryDirectory(
        prefix="snowin_isce3_icu_", dir=output_path.parent
    ) as tmp:
        work = Path(tmp)
        wrapped_raster_path = work / "wrapped.tif"
        coherence_raster_path = work / "coherence.tif"
        unwrapped_raster_path = work / "unwrapped.tif"
        components_raster_path = work / "components.tif"
        _write_raster(
            wrapped_raster_path,
            igram,
            epsg=epsg,
            x0_center=float(x_crop[0]),
            y0_center=float(y_crop[0]),
            dx=dx,
            dy=dy,
            data_type=gdal.GDT_CFloat32,
        )
        _write_raster(
            coherence_raster_path,
            coherence,
            epsg=epsg,
            x0_center=float(x_crop[0]),
            y0_center=float(y_crop[0]),
            dx=dx,
            dy=dy,
            data_type=gdal.GDT_Float32,
        )
        _write_raster(
            unwrapped_raster_path,
            np.zeros(igram.shape, dtype=np.float32),
            epsg=epsg,
            x0_center=float(x_crop[0]),
            y0_center=float(y_crop[0]),
            dx=dx,
            dy=dy,
            data_type=gdal.GDT_Float32,
            nodata=float("nan"),
        )
        _write_raster(
            components_raster_path,
            np.zeros(igram.shape, dtype=np.uint32),
            epsg=epsg,
            x0_center=float(x_crop[0]),
            y0_center=float(y_crop[0]),
            dx=dx,
            dy=dy,
            data_type=gdal.GDT_UInt32,
        )

        unw_raster = isce3.io.Raster(str(unwrapped_raster_path), update=True)
        components_raster = isce3.io.Raster(str(components_raster_path), update=True)
        igram_raster = isce3.io.Raster(str(wrapped_raster_path))
        coherence_raster = isce3.io.Raster(str(coherence_raster_path))
        isce3.unwrap.ICU().unwrap(
            unw_raster,
            components_raster,
            igram_raster,
            coherence_raster,
            seed=0,
        )
        unw_raster.close_dataset()
        components_raster.close_dataset()
        igram_raster.close_dataset()
        coherence_raster.close_dataset()

        unw_ds = gdal.Open(str(unwrapped_raster_path), gdal.GA_Update)
        unwrapped = unw_ds.GetRasterBand(1).ReadAsArray()
        unwrapped[~valid] = np.nan
        out_band = unw_ds.GetRasterBand(1)
        out_band.WriteArray(unwrapped)
        unw_ds.SetMetadata(
            {
                "source_product": gunw_path.name,
                "source_layer": f"/{WRAPPED_GROUP}/wrappedInterferogram",
                "unwrap_algorithm": "ISCE3 ICU",
                "phase_orientation": "reference_minus_secondary (source GUNW orientation)",
                "aoi_epsg4326": ",".join(str(value) for value in aoi),
                "valid_pixel_count": str(int(valid.sum())),
                "isce3_version": str(isce3.__version__),
            }
        )
        unw_ds.FlushCache()
        unw_ds = None

        final_unw = work / output_path.name
        final_cc = work / conncomp_path.name
        unwrapped_raster_path.replace(final_unw)
        components_raster_path.replace(final_cc)
        final_unw.replace(output_path)
        final_cc.replace(conncomp_path)

    return output_path, conncomp_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gunw", type=Path, help="operational NISAR GUNW HDF5 product")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("nival_20m_isce3_icu.tif"),
        help="output unwrapped-phase GeoTIFF",
    )
    parser.add_argument(
        "--aoi",
        nargs=4,
        type=float,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        default=DEFAULT_AOI,
        help="crop box in EPSG:4326 (default: Mores Creek study area)",
    )
    args = parser.parse_args()
    if not args.gunw.is_file():
        raise FileNotFoundError(args.gunw)
    output, components = unwrap_gunw_20m(args.gunw, args.output, aoi=tuple(args.aoi))
    print(f"ISCE3 ICU unwrapped phase: {output}")
    print(f"ISCE3 ICU connected components: {components}")


if __name__ == "__main__":
    main()
