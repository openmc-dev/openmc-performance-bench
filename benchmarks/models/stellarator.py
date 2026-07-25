"""DAGMC model of the Eos neutron-source stellarator."""

from __future__ import annotations

import gzip
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from urllib.request import Request, urlopen

import openmc

BENCHMARK_NAME = "Stellarator"

_MODEL_DIR = Path(__file__).resolve().parent
_XML_PATH = _MODEL_DIR / "stellarator.xml"
_H5M_PATH = _MODEL_DIR / "Eos.h5m"
_H5M_URL = (
    "https://zenodo.org/api/records/21577573/files/Eos.h5m.gz/content"
)
_H5M_GZIP_SIZE = 51_111_490
_H5M_GZIP_MD5 = "ecf35ab1a019374f9ff447849b03873f"


def _download_geometry() -> None:
    """Download, verify, and atomically install the stellarator DAGMC mesh."""
    compressed_path: Path | None = None
    decompressed_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            dir=_MODEL_DIR, prefix=".Eos-", suffix=".h5m.gz", delete=False
        ) as compressed:
            compressed_path = Path(compressed.name)
            digest = hashlib.md5(usedforsecurity=False)
            request = Request(
                _H5M_URL,
                headers={"User-Agent": "openmc-performance-bench"},
            )
            with urlopen(request, timeout=60) as response:
                while chunk := response.read(1024 * 1024):
                    compressed.write(chunk)
                    digest.update(chunk)

        downloaded_size = compressed_path.stat().st_size
        if downloaded_size != _H5M_GZIP_SIZE:
            raise RuntimeError(
                "Downloaded Eos.h5m.gz has the wrong size: "
                f"expected {_H5M_GZIP_SIZE} bytes, got {downloaded_size}"
            )
        if digest.hexdigest() != _H5M_GZIP_MD5:
            raise RuntimeError(
                "Downloaded Eos.h5m.gz failed its Zenodo checksum"
            )

        with tempfile.NamedTemporaryFile(
            dir=_MODEL_DIR, prefix=".Eos-", suffix=".h5m", delete=False
        ) as decompressed:
            decompressed_path = Path(decompressed.name)
            with gzip.open(compressed_path, "rb") as source:
                shutil.copyfileobj(source, decompressed)

        os.replace(decompressed_path, _H5M_PATH)
        decompressed_path = None
    finally:
        if compressed_path is not None:
            compressed_path.unlink(missing_ok=True)
        if decompressed_path is not None:
            decompressed_path.unlink(missing_ok=True)


def _ensure_geometry() -> Path:
    """Return the local DAGMC mesh, downloading it when necessary."""
    if not _H5M_PATH.is_file():
        _download_geometry()
    return _H5M_PATH


def build_model() -> openmc.Model:
    h5m_path = _ensure_geometry()
    model = openmc.Model.from_model_xml(_XML_PATH)

    # ASV exports the model into a temporary directory, so the relative
    # filename from stellarator.xml needs to be made absolute.
    for universe in model.geometry.get_all_universes().values():
        if isinstance(universe, openmc.DAGMCUniverse):
            universe.filename = str(h5m_path)

    return model
