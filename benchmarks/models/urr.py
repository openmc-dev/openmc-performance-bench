"""ICSBEP IEU-MET-FAST-007 Case 4 model for URR benchmarking"""

from __future__ import annotations

import openmc
import numpy as np

BENCHMARK_NAME = "URR"


def build_model() -> openmc.Model:
    # Homogenized HEU, natural U, and voids
    mat1 = openmc.Material(name="HEU/NatU/Voids")
    mat1.set_density('sum')
    mat1.add_nuclide("U234", 5.4058e-5)
    mat1.add_nuclide("U235", 4.9831e-3)
    mat1.add_nuclide("U236", 1.3733e-5)
    mat1.add_nuclide("U238", 4.3108e-2)

    # Intermediate enriched Uranium (10 wt%)
    mat2 = openmc.Material(name="Intermediate Enriched U")
    mat2.set_density('sum')
    mat2.add_nuclide("U234", 2.4761e-5)
    mat2.add_nuclide("U235", 4.8461e-3)
    mat2.add_nuclide("U236", 4.3348e-5)
    mat2.add_nuclide("U238", 4.2695e-2)

    # Natural Uranium
    mat3 = openmc.Material(name="Natural U")
    mat3.set_density('sum')
    mat3.add_nuclide("U234", 2.6518e-6)
    mat3.add_nuclide("U235", 3.4701e-4)
    mat3.add_nuclide("U238", 4.7846e-2)

    # Depleted Uranium
    mat4 = openmc.Material(name="Depleted U")
    mat4.set_density('sum')
    mat4.add_nuclide("U234", 2.8672e-7)
    mat4.add_nuclide("U235", 1.0058e-4)
    mat4.add_nuclide("U236", 1.1468e-6)
    mat4.add_nuclide("U238", 4.7677e-2)

    # Create materials
    materials = openmc.Materials([mat1, mat2, mat3, mat4])

    # Define z-cylinders
    cyl1 = openmc.ZCylinder(r=2.25014)
    cyl2 = openmc.ZCylinder(r=3.10996)
    cyl3 = openmc.ZCylinder(r=7.62)
    cyl4 = openmc.ZCylinder(r=12.54604)
    cyl5 = openmc.ZCylinder(r=26.67)
    cyl6 = openmc.ZCylinder(r=41.91, boundary_type='vacuum')

    # Define z-planes
    z1 = openmc.ZPlane(z0=-57.46750, boundary_type='vacuum')
    z2 = openmc.ZPlane(z0=-41.73361)
    z3 = openmc.ZPlane(z0=-38.24644)
    z4 = openmc.ZPlane(z0=-22.39010)
    z5 = openmc.ZPlane(z0=4.35102)
    z6 = openmc.ZPlane(z0=17.16665)
    z7 = openmc.ZPlane(z0=23.81250)
    z8 = openmc.ZPlane(z0=39.05250, boundary_type='vacuum')

    # Define cells
    cells = []
    cells.append(openmc.Cell(fill=mat2, region=-cyl3 & +z2 & -z4))
    cells.append(openmc.Cell(fill=mat2, region=-cyl4 & +z4 & -z5))
    cells.append(openmc.Cell(fill=mat2, region=-cyl2 & +z5 & -z7))
    cells.append(openmc.Cell(fill=mat2, region=-cyl1 & +z7 & -z8))
    cells.append(openmc.Cell(fill=mat3, region=+cyl3 & -cyl5 & +z2 & -z3))
    cells.append(openmc.Cell(fill=mat1, region=+cyl3 & -cyl5 & +z3 & -z4))
    cells.append(openmc.Cell(fill=mat1, region=+cyl4 & -cyl5 & +z4 & -z5))
    cells.append(openmc.Cell(fill=mat1, region=+cyl2 & -cyl5 & +z5 & -z6))
    cells.append(openmc.Cell(fill=mat3, region=+cyl2 & -cyl5 & +z6 & -z7))
    cells.append(openmc.Cell(fill=mat4, region=+cyl5 & -cyl6 & +z1 & -z8))
    cells.append(openmc.Cell(fill=mat4, region=-cyl5 & +z1 & -z2))
    cells.append(openmc.Cell(fill=mat4, region=+cyl1 & -cyl5 & +z7 & -z8))

    # Create the geometry
    geometry = openmc.Geometry(cells=cells)

    # Settings with eigenvalue run and box source
    settings = openmc.Settings()
    settings.run_mode = 'eigenvalue'
    settings.batches = 3000
    settings.inactive = 20
    settings.particles = 10000
    settings.source = openmc.IndependentSource()

    return openmc.Model(geometry=geometry, settings=settings)
