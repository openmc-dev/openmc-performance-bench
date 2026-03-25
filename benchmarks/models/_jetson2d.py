"""Shared Jetson 2D model builder for FW-CADIS benchmark suite.

This is a highly simplified 2D cylindrical model inspired by the Joint European
Torus (JET).  The torus cross-section and 2.5 m thick concrete bio-shield with
30 cm borated concrete liner are approximated with concentric ZCylinders inside
a rectangular room.  Overall problem dimension is 40 m x 40 m.
"""

from __future__ import annotations

import contextlib
import glob
import os
from pathlib import Path

import numpy as np
import openmc
import openmc.mgxs
import openmc.stats


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

R0_PLASMA = 296.0   # Major radius (cm)
A_PLASMA = 210.0    # Minor radius (cm)
RO = 2000           # Outer room half-width (cm)
MESH_DIM = 400      # Mesh bins per axis (10 cm resolution)


# ---------------------------------------------------------------------------
# Context manager for temporary chdir
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _chdir(path: Path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


# ---------------------------------------------------------------------------
# Custom metric helpers (used by MC analog and MC WW benchmarks)
# ---------------------------------------------------------------------------

def _open_statepoint(result):
    """Find and open the statepoint file in the working directory."""
    paths = glob.glob(str(result.workdir / "statepoint.*.h5"))
    if not paths:
        raise FileNotFoundError(f"No statepoint file found in {result.workdir}")
    return openmc.StatePoint(paths[0])


def _get_rel_err(result):
    """Return relative error array from the mesh_flux tally."""
    sp = _open_statepoint(result)
    tally = sp.get_tally(name="mesh_flux")
    rel_err = tally.get_slice(scores=["flux"]).get_values(value="rel_err")
    rel_err = np.nan_to_num(rel_err, nan=1.0, posinf=1.0, neginf=1.0)
    sp.close()
    return rel_err


def avg_rel_error(result):
    """Average relative error (%) across all mesh cells."""
    return float(np.mean(_get_rel_err(result)) * 100.0)


def max_rel_error(result):
    """Maximum relative error (%) across all mesh cells."""
    return float(np.max(_get_rel_err(result)) * 100.0)


def pct_cells_with_tallies(result):
    """Percentage of mesh cells that received at least one tally score."""
    rel_err = _get_rel_err(result)
    unhit = np.sum(rel_err == 1.0)
    return float(100.0 - (unhit / rel_err.size) * 100.0)


def figure_of_merit(result):
    """FOM = 1 / (R^2 * T) where R = avg relative error, T = transport time."""
    rel_err = _get_rel_err(result)
    r = float(np.mean(rel_err))
    t = result.timing_stats.transport if result.timing_stats else None
    if t is None or t <= 0 or r <= 0:
        return float("nan")
    return 1.0 / (r * r * t)


MC_CUSTOM_METRICS = {
    "avg_rel_error": avg_rel_error,
    "max_rel_error": max_rel_error,
    "pct_cells_with_tallies": pct_cells_with_tallies,
    "figure_of_merit": figure_of_merit,
}


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def _build_materials():
    mat_inconel = openmc.Material(name="Inconel600")
    mat_inconel.add_element("Ni", 0.75)
    mat_inconel.add_element("Fe", 0.10)
    mat_inconel.add_element("Cr", 0.15)
    mat_inconel.set_density("g/cm3", 8.0)

    mat_steel = openmc.Material(name="SS304B7")
    mat_steel.add_element("Fe", 0.67)
    mat_steel.add_element("Cr", 0.20)
    mat_steel.add_element("Ni", 0.12)
    mat_steel.add_nuclide("B10", 0.01)
    mat_steel.set_density("g/cm3", 7.8)

    mat_water = openmc.Material(name="H2O")
    mat_water.add_nuclide("H1", 2)
    mat_water.add_nuclide("O16", 1)
    mat_water.set_density("g/cm3", 1.0)

    mat_concrete = openmc.Material(name="Concrete")
    mat_concrete.set_density("g/cm3", 2.3)
    mat_concrete.add_nuclide("H1", 0.20)
    mat_concrete.add_nuclide("O16", 0.10)
    mat_concrete.add_element("Si", 0.24)
    mat_concrete.add_element("Ca", 0.18)
    mat_concrete.add_element("Al", 0.02)
    mat_concrete.add_element("C", 0.01)

    borated_concrete = openmc.Material(name="BoroConcrete")
    borated_concrete.add_nuclide("Si28", 0.185, "wo")
    borated_concrete.add_nuclide("Si29", 0.0097, "wo")
    borated_concrete.add_nuclide("Si30", 0.0063, "wo")
    borated_concrete.add_nuclide("Ca40", 0.158, "wo")
    borated_concrete.add_nuclide("Ca42", 0.00105, "wo")
    borated_concrete.add_nuclide("Ca43", 0.00022, "wo")
    borated_concrete.add_nuclide("Ca44", 0.00340, "wo")
    borated_concrete.add_nuclide("Ca46", 0.0000065, "wo")
    borated_concrete.add_nuclide("Ca48", 0.00030, "wo")
    borated_concrete.add_nuclide("Al27", 0.045, "wo")
    borated_concrete.add_nuclide("Fe54", 0.0032, "wo")
    borated_concrete.add_nuclide("Fe56", 0.0502, "wo")
    borated_concrete.add_nuclide("Fe57", 0.0012, "wo")
    borated_concrete.add_nuclide("Fe58", 0.00015, "wo")
    borated_concrete.add_nuclide("Mg24", 0.0079, "wo")
    borated_concrete.add_nuclide("Mg25", 0.0010, "wo")
    borated_concrete.add_nuclide("Mg26", 0.0011, "wo")
    borated_concrete.add_nuclide("K39", 0.0185, "wo")
    borated_concrete.add_nuclide("K40", 0.0000023, "wo")
    borated_concrete.add_nuclide("K41", 0.00134, "wo")
    borated_concrete.add_nuclide("Na23", 0.015, "wo")
    borated_concrete.add_element("O", 0.455, "wo")
    borated_concrete.add_nuclide("H1", 0.008, "wo")
    borated_concrete.add_nuclide("H2", 0.0000012, "wo")
    borated_concrete.add_element("C", 0.00101, "wo")
    borated_concrete.add_nuclide("B10", 0.00199, "wo")
    borated_concrete.add_nuclide("B11", 0.00801, "wo")
    borated_concrete.add_nuclide("S32", 0.00095, "wo")
    borated_concrete.add_nuclide("S33", 0.0000076, "wo")
    borated_concrete.add_nuclide("S34", 0.000043, "wo")
    borated_concrete.add_nuclide("S36", 0.0000000002, "wo")
    borated_concrete.add_nuclide("Ti46", 0.000082, "wo")
    borated_concrete.add_nuclide("Ti47", 0.000074, "wo")
    borated_concrete.add_nuclide("Ti48", 0.00073, "wo")
    borated_concrete.add_nuclide("Ti49", 0.000054, "wo")
    borated_concrete.add_nuclide("Ti50", 0.000052, "wo")
    borated_concrete.add_nuclide("Mn55", 0.0005, "wo")
    borated_concrete.set_density("g/cm3", 2.3)

    mat_air = openmc.Material(name="Air")
    mat_air.set_density("g/cm3", 0.001225)
    mat_air.add_element("N", 0.78084, "ao")
    mat_air.add_element("O", 0.20946, "ao")
    mat_air.add_element("Ar", 0.00934, "ao")
    mat_air.add_element("C", 0.00036, "ao")

    mats = openmc.Materials([
        mat_inconel, mat_steel, mat_water,
        mat_concrete, borated_concrete, mat_air,
    ])
    return mats, mat_inconel, mat_steel, mat_water, mat_concrete, borated_concrete, mat_air


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _build_geometry(mat_inconel, mat_steel, mat_water, mat_concrete,
                    borated_concrete, mat_air):
    cwt = A_PLASMA + 1.5
    st = cwt + 22
    ct = st + 18
    owti = ct + 1.5

    # Inner wall surfaces
    inner_air_outer = openmc.ZCylinder(r=R0_PLASMA - owti)
    inner_wrapper_outer = openmc.ZCylinder(r=R0_PLASMA - ct)
    inner_coolant_outer = openmc.ZCylinder(r=R0_PLASMA - st)
    inner_shield_outer = openmc.ZCylinder(r=R0_PLASMA - cwt)
    inner_chamber_outer = openmc.ZCylinder(r=R0_PLASMA - A_PLASMA)

    # Outer wall surfaces
    outer_chamber_inner = openmc.ZCylinder(r=R0_PLASMA + A_PLASMA)
    outer_shield_inner = openmc.ZCylinder(r=R0_PLASMA + cwt)
    outer_coolant_inner = openmc.ZCylinder(r=R0_PLASMA + st)
    outer_wrapper_inner = openmc.ZCylinder(r=R0_PLASMA + ct)
    outer_air_inner = openmc.ZCylinder(r=R0_PLASMA + owti)

    # Room boundaries
    li, lo = 1720, 1750
    room_liner_inner = openmc.model.RectangularParallelepiped(
        xmin=-li, xmax=li, ymin=-li, ymax=li, zmin=-li, zmax=li,
    )
    room_liner_outer = openmc.model.RectangularParallelepiped(
        xmin=-lo, xmax=lo, ymin=-lo, ymax=lo, zmin=-lo, zmax=lo,
    )
    x_min = openmc.XPlane(-RO, boundary_type="vacuum")
    x_max = openmc.XPlane(RO, boundary_type="vacuum")
    y_min = openmc.YPlane(-RO, boundary_type="vacuum")
    y_max = openmc.YPlane(RO, boundary_type="vacuum")

    # Cells
    plasma_cell = openmc.Cell(name="Plasma",
                              region=+inner_chamber_outer & -outer_chamber_inner,
                              fill=None)

    cells = [
        openmc.Cell(name="Central Air",
                    region=-inner_air_outer, fill=mat_air),
        openmc.Cell(name="Inner Wrapper",
                    region=+inner_air_outer & -inner_wrapper_outer,
                    fill=mat_inconel),
        openmc.Cell(name="Inner Coolant",
                    region=+inner_wrapper_outer & -inner_coolant_outer,
                    fill=mat_water),
        openmc.Cell(name="Inner Shield",
                    region=+inner_coolant_outer & -inner_shield_outer,
                    fill=mat_steel),
        openmc.Cell(name="Inner Chamber Wall",
                    region=+inner_shield_outer & -inner_chamber_outer,
                    fill=mat_inconel),
        plasma_cell,
        openmc.Cell(name="Outer Chamber Wall",
                    region=+outer_chamber_inner & -outer_shield_inner,
                    fill=mat_inconel),
        openmc.Cell(name="Outer Shield",
                    region=+outer_shield_inner & -outer_coolant_inner,
                    fill=mat_steel),
        openmc.Cell(name="Outer Coolant",
                    region=+outer_coolant_inner & -outer_wrapper_inner,
                    fill=mat_water),
        openmc.Cell(name="Outer Wrapper",
                    region=+outer_wrapper_inner & -outer_air_inner,
                    fill=mat_inconel),
        openmc.Cell(name="Air",
                    region=+outer_air_inner & -room_liner_inner,
                    fill=mat_air),
        openmc.Cell(name="Concrete Liner",
                    region=+room_liner_inner & -room_liner_outer,
                    fill=borated_concrete),
        openmc.Cell(name="Concrete Wall",
                    region=+room_liner_outer & +x_min & -x_max & +y_min & -y_max,
                    fill=mat_concrete),
    ]

    root_universe = openmc.Universe(cells=cells)
    geometry = openmc.Geometry(root_universe)
    return geometry, plasma_cell


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_base_model():
    """Build the Jetson 2D base model.

    Returns
    -------
    model : openmc.Model
        Continuous-energy fixed-source model with mesh flux tally.
    mesh : openmc.RegularMesh
        The 400x400 tally mesh (reused for random ray source regions / WW).
    plasma_cell : openmc.Cell
        The plasma cell (used as source domain constraint).
    """
    mats, mat_inconel, mat_steel, mat_water, mat_concrete, borated_concrete, mat_air = (
        _build_materials()
    )
    geometry, plasma_cell = _build_geometry(
        mat_inconel, mat_steel, mat_water, mat_concrete, borated_concrete, mat_air,
    )

    # Source
    source = openmc.IndependentSource()
    source.space = openmc.stats.Box(
        lower_left=[-R0_PLASMA, -R0_PLASMA, -R0_PLASMA],
        upper_right=[R0_PLASMA, R0_PLASMA, R0_PLASMA],
        only_fissionable=False,
    )
    source.constraints = {"domains": [plasma_cell]}
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.Discrete([2449632.3277176125], [1.0])

    # Settings
    settings = openmc.Settings()
    settings.source = source
    settings.batches = 50
    settings.particles = 4500
    settings.run_mode = "fixed source"

    # Mesh & tallies
    mesh = openmc.RegularMesh()
    mesh.dimension = [MESH_DIM, MESH_DIM]
    mesh.lower_left = [-RO, -RO]
    mesh.upper_right = [RO, RO]

    tallies = openmc.Tallies()
    mesh_tally = openmc.Tally(name="mesh_flux")
    mesh_tally.filters = [openmc.MeshFilter(mesh)]
    mesh_tally.scores = ["flux"]
    tallies.append(mesh_tally)

    model = openmc.Model(
        geometry=geometry, materials=mats,
        settings=settings, tallies=tallies,
    )
    return model, mesh, plasma_cell
