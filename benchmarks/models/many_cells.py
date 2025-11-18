"""OpenMC model of complex geometry with many cells."""

from __future__ import annotations

import numpy as np
from scipy.spatial import Delaunay
from scipy.stats import qmc
import openmc

BENCHMARK_NAME = "ManyCells"


def build_model() -> openmc.Model:
    cube_corners = np.array([
        [0, 0, 0],
        [0, 0, 1],
        [0, 1, 0],
        [0, 1, 1],
        [1, 0, 0],
        [1, 0, 1],
        [1, 1, 0],
        [1, 1, 1]
    ])

    # Generate interior points using a Sobol sequence
    seed = 12345
    sobol_engine = qmc.Sobol(3, seed=seed)
    interior_points = sobol_engine.random_base2(10)

    # For convenience, define a function that returns n Sobol samples in 2D
    def get_sobol_2d_samples(m, seed):
        sampler = qmc.Sobol(d=2, seed=seed)
        return sampler.random_base2(m)

    xy = get_sobol_2d_samples(3, seed)
    face_x0 = np.column_stack((np.zeros(2**3), xy[:, 0], xy[:, 1]))
    xy = get_sobol_2d_samples(3, seed + 1)
    face_x1 = np.column_stack((np.ones(2**3), xy[:, 0], xy[:, 1]))
    xy = get_sobol_2d_samples(3, seed + 2)
    face_y0 = np.column_stack((xy[:, 0], np.zeros(2**3), xy[:, 1]))
    xy = get_sobol_2d_samples(3, seed + 3)
    face_y1 = np.column_stack((xy[:, 0], np.ones(2**3), xy[:, 1]))
    xy = get_sobol_2d_samples(3, seed + 4)
    face_z0 = np.column_stack((xy[:, 0], xy[:, 1], np.zeros(2**3)))
    xy = get_sobol_2d_samples(3, seed + 5)
    face_z1 = np.column_stack((xy[:, 0], xy[:, 1], np.ones(2**3)))

    # Combine corners and interior points
    points = np.vstack([
        cube_corners,
        interior_points,
        face_x0,
        face_x1,
        face_y0,
        face_y1,
        face_z0,
        face_z1
    ])

    # Scale points to cover [-10, 10]^3
    points -= 0.5
    points *= 20

    # Create the Delaunay tetrahedralization
    tri = Delaunay(points)

    # Create list to store each tetrahedron as an OpenMC Cell
    cells = []

    for simplex in tri.simplices:
        # 4 vertices of the tetrahedron
        p0 = points[simplex[0]]
        p1 = points[simplex[1]]
        p2 = points[simplex[2]]
        p3 = points[simplex[3]]

        # 3-point faces of the tetrahedron
        faces = [
            (p0, p1, p2),
            (p0, p1, p3),
            (p0, p2, p3),
            (p1, p2, p3),
        ]

        # We need the centroid to determine which side of each plane is "inside"
        centroid = (p0 + p1 + p2 + p3) / 4.0

        # Create planes and figure out orientation for each face
        region_parts = []
        for (fp1, fp2, fp3) in faces:
            plane = openmc.Plane.from_points(fp1, fp2, fp3)

            # Turn into canonical form
            plane.a, plane.b, plane.c, plane.d = plane.normalize()

            # Evaluate the plane equation at the tetrahedron's centroid
            # plane.evaluate(x) > 0 => the point x is on the +plane side
            region_part = +plane if plane.evaluate(centroid) > 0 else -plane
            region_parts.append(region_part)

        # Create material for this cell
        m = openmc.Material()
        m.add_nuclide('H1', 1.0)
        m.set_density('g/cm3', 1.0e-10)

        # Create a cell corresponding to this tetrahedron
        cell = openmc.Cell(fill=m, region=openmc.Intersection(region_parts))
        cells.append(cell)

    # Now you have a list of OpenMC cells, each one a tetrahedron.
    # You could add them to an OpenMC universe or geometry as you normally would.
    geometry = openmc.Geometry(cells, merge_surfaces=True)
    for plane in geometry.get_all_surfaces().values():
        if (np.abs(plane._get_normal()) > 1e-12).sum() == 1:
            plane.boundary_type = 'vacuum'

    # Isotropic source uniformly distributed in the domain
    source = openmc.IndependentSource()
    source.space = openmc.stats.Box((-10.0, -10.0, -10.0), (10.0, 10.0, 10.0))
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.delta_function(1.0e6)

    # Settings with fixed source run
    settings = openmc.Settings()
    settings.batches = 10
    settings.particles = 10_000
    settings.run_mode = "fixed source"
    settings.source = source

    return openmc.Model(geometry=geometry, settings=settings)
