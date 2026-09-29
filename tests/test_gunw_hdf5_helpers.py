import numpy as np
import pytest

from snowin.io._nisar_hdf5 import decode_hdf5_scalar, read_attrs_hdf5, read_scalar_hdf5


def test_decode_hdf5_scalar_values():
    assert decode_hdf5_scalar(np.asarray(b"snow")) == "snow"
    assert decode_hdf5_scalar(np.array([b"a", b"b"])) == ["a", "b"]
    assert decode_hdf5_scalar(np.float32(2.5)) == pytest.approx(2.5)


def test_hdf5_scalar_and_attribute_readers(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "metadata.h5"
    with h5py.File(path, "w") as h5:
        variable = h5.create_dataset("track", data=np.int32(42))
        variable.attrs["label"] = np.bytes_(b"track-number")
        h5.create_dataset("name", data=np.bytes_(b"synthetic-granule"))

    assert read_scalar_hdf5(path, "name") == "synthetic-granule"
    assert read_scalar_hdf5(path, "missing") is None
    assert read_attrs_hdf5(path, "track") == {"label": "track-number"}
    assert read_attrs_hdf5(path, "missing") == {}
