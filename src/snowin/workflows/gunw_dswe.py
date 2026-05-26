"""Controlled NISAR GUNW-to-dSWE workflow scaffold."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import csv
import json
import subprocess
from importlib.metadata import PackageNotFoundError, version

import matplotlib.pyplot as plt
import numpy as np

from snowin.corrections import PhaseCorrectionConfig, apply_phase_corrections
from snowin.io.gunw import read_gunw_layers
from snowin.quality import build_gunw_quality_mask
from snowin.reference import apply_reference_phase
from snowin.utils import dataarray_to_numpy
from snowin.workflows.dswe import DsweRasterResult, phase_raster_to_dswe


def _package_version() -> str | None:
    try:
        return version("snowin")
    except PackageNotFoundError:
        return None


def _git_commit(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path.parent), "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


@dataclass(frozen=True)
class DsweConfig:
    """Configuration for phase-to-dSWE conversion."""

    method: str = "oveisgharan"
    sensor: str | None = "nisar"
    band: str | None = "L"
    wavelength_m: float | None = None
    incidence_angle_unit: str | None = "auto"
    snow_density_g_cm3: float | None = None
    output_unit: str = "cm"
    incidence_shape_policy: str = "fail"


@dataclass(frozen=True)
class QualityConfig:
    """Configuration for GUNW quality masking."""

    coherence_min: float = 0.3
    connected_component: str | int | None = "dominant"
    mask_fill_values: tuple[int | float, ...] = (255,)


@dataclass(frozen=True)
class ReferenceConfig:
    """Configuration for reference-phase handling."""

    strategy: str = "none"


@dataclass(frozen=True)
class GunwDsweResult:
    """Outputs from the controlled GUNW-to-dSWE scaffold."""

    dswe: np.ndarray
    phase_raw: np.ndarray
    phase_corrected: np.ndarray
    phase_referenced: np.ndarray
    valid_mask: np.ndarray
    metadata: dict[str, Any]
    diagnostics: dict[str, Any]
    output_paths: dict[str, Path]


def _write_json(path: Path, obj: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)
    return path


def _write_diagnostics_csv(path: Path, diagnostics: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for section, values in diagnostics.items():
        if isinstance(values, dict):
            for key, value in values.items():
                rows.append({"section": section, "metric": key, "value": value})
        else:
            rows.append({"section": "workflow", "metric": section, "value": values})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["section", "metric", "value"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_dswe_png(path: Path, dswe: np.ndarray, unit: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    finite = dswe[np.isfinite(dswe)]
    if finite.size == 0:
        raise ValueError("Cannot plot dSWE because it has no finite values.")
    vmin, vmax = np.nanpercentile(finite, [2, 98])
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(dswe, vmin=vmin, vmax=vmax, cmap="RdBu")
    ax.set_title(
        "GUNW dSWE demonstration\ncorrection/reference choices recorded in diagnostics"
    )
    ax.set_xticks([])
    ax.set_yticks([])
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label(f"dSWE ({unit})")
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def gunw_to_dswe(
    gunw_file,
    *,
    out_dir=None,
    pol: str | None = None,
    crop_geojson=None,
    quality_config: QualityConfig | dict[str, Any] | None = None,
    correction_config: PhaseCorrectionConfig | dict[str, Any] | None = None,
    reference_config: ReferenceConfig | dict[str, Any] | None = None,
    dswe_config: DsweConfig | dict[str, Any] | None = None,
    write_outputs: bool = True,
) -> GunwDsweResult:
    """Run an explicit, provenance-heavy GUNW-to-dSWE scaffold.

    This is not a validated production SWE algorithm. It wires together tested
    IO, quality-mask, correction, reference, and phase-to-dSWE functions while
    preserving every assumption in diagnostics.
    """
    if crop_geojson is not None:
        raise NotImplementedError(
            "crop_geojson is reserved for a later centralized raster crop/mask utility. "
            "Use plot_gunw() for cropped quicklooks for now."
        )

    qcfg = (
        quality_config
        if isinstance(quality_config, QualityConfig)
        else QualityConfig(**(quality_config or {}))
    )
    ccfg = (
        correction_config
        if isinstance(correction_config, PhaseCorrectionConfig)
        else PhaseCorrectionConfig(**(correction_config or {}))
    )
    rcfg = (
        reference_config
        if isinstance(reference_config, ReferenceConfig)
        else ReferenceConfig(**(reference_config or {}))
    )
    dcfg = (
        dswe_config
        if isinstance(dswe_config, DsweConfig)
        else DsweConfig(**(dswe_config or {}))
    )

    gunw = read_gunw_layers(gunw_file, pol=pol)
    layers = gunw.layers
    if layers.get("unwrapped_phase") is None:
        raise ValueError("GUNW product does not contain unwrapped_phase.")
    if layers.get("incidence_angle") is None:
        raise ValueError("GUNW product does not contain incidence_angle.")

    phase_raw = dataarray_to_numpy(layers["unwrapped_phase"])
    incidence_angle = dataarray_to_numpy(layers["incidence_angle"])
    coherence = (
        dataarray_to_numpy(layers["coherence_unw"])
        if layers.get("coherence_unw") is not None
        else None
    )
    connected = (
        dataarray_to_numpy(layers["connected_components"])
        if layers.get("connected_components") is not None
        else None
    )
    gunw_mask = (
        dataarray_to_numpy(layers["mask"]) if layers.get("mask") is not None else None
    )

    quality = build_gunw_quality_mask(
        phase_raw,
        coherence=coherence,
        connected_components=connected,
        gunw_mask=gunw_mask,
        coherence_min=qcfg.coherence_min,
        connected_component=qcfg.connected_component,
        mask_fill_values=qcfg.mask_fill_values,
    )

    ionosphere = (
        dataarray_to_numpy(layers["ionosphere"])
        if layers.get("ionosphere") is not None
        else None
    )
    wet_tropo = (
        dataarray_to_numpy(layers["wet_tropo"])
        if layers.get("wet_tropo") is not None
        else None
    )
    hydro_tropo = (
        dataarray_to_numpy(layers["hydro_tropo"])
        if layers.get("hydro_tropo") is not None
        else None
    )
    corrected = apply_phase_corrections(
        phase_raw,
        ionosphere=ionosphere,
        wet_tropo=wet_tropo,
        hydro_tropo=hydro_tropo,
        config=ccfg,
        valid_mask=quality.valid_mask,
    )
    referenced = apply_reference_phase(
        corrected.phase_corrected,
        strategy=rcfg.strategy,  # type: ignore[arg-type]
        valid_mask=quality.valid_mask,
    )
    dswe_result: DsweRasterResult = phase_raster_to_dswe(
        referenced.phase_referenced,
        incidence_angle,
        method=dcfg.method,
        sensor=dcfg.sensor,
        band=dcfg.band,
        wavelength_m=dcfg.wavelength_m,
        incidence_angle_unit=dcfg.incidence_angle_unit,
        snow_density_g_cm3=dcfg.snow_density_g_cm3,
        output_unit=dcfg.output_unit,  # type: ignore[arg-type]
        incidence_shape_policy=dcfg.incidence_shape_policy,  # type: ignore[arg-type]
    )
    dswe = dswe_result.dswe.copy()
    dswe[~quality.valid_mask] = np.nan

    metadata = {
        **gunw.metadata,
        "quality_config": asdict(qcfg),
        "correction_config": asdict(ccfg),
        "reference_config": asdict(rcfg),
        "dswe_config": asdict(dcfg),
        "workflow": "gunw_to_dswe",
        "snowin_version": _package_version(),
        "git_commit": _git_commit(Path(__file__).resolve()),
        "validated_science_product": False,
    }
    diagnostics = {
        "quality": quality.diagnostics,
        "corrections": corrected.diagnostics,
        "reference": referenced.diagnostics,
        "dswe": {
            **dswe_result.diagnostics,
            "post_quality_mask_valid_pixels": int(np.isfinite(dswe).sum()),
        },
    }

    output_paths: dict[str, Path] = {}
    if write_outputs:
        if out_dir is None:
            raise ValueError("out_dir is required when write_outputs=True.")
        out_path = Path(out_dir).expanduser().resolve()
        out_path.mkdir(parents=True, exist_ok=True)
        stem = f"{Path(gunw.gunw_file).stem}_{gunw.polarization}_dswe_demo"
        output_paths["diagnostics_json"] = _write_json(
            out_path / f"{stem}_diagnostics.json", diagnostics
        )
        output_paths["metadata_json"] = _write_json(
            out_path / f"{stem}_metadata.json", metadata
        )
        output_paths["diagnostics_csv"] = _write_diagnostics_csv(
            out_path / f"{stem}_diagnostics.csv", diagnostics
        )
        output_paths["dswe_png"] = _write_dswe_png(
            out_path / f"{stem}.png", dswe, dswe_result.unit
        )

    return GunwDsweResult(
        dswe=dswe,
        phase_raw=phase_raw,
        phase_corrected=corrected.phase_corrected,
        phase_referenced=referenced.phase_referenced,
        valid_mask=quality.valid_mask,
        metadata=metadata,
        diagnostics=diagnostics,
        output_paths=output_paths,
    )
