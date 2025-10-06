"""Repeated slabs with many nuclides"""

from __future__ import annotations

import openmc
import numpy as np

BENCHMARK_NAME = "CrossSectionLookups"


def build_model() -> openmc.Model:
    # Define materials
    fuel = openmc.Material(name='Fuel')
    fuel.set_density('g/cm3', 10.062)
    # main actinides and other specified nuclides
    components = {
        "U234": 4.9476e-6,
        "U235": 4.8218e-4,
        "U236": 9.0402e-5,
        "U238": 2.1504e-2,
        "Np237": 7.3733e-6,
        "Pu238": 1.5148e-6,
        "Pu239": 1.3955e-4,
        "Pu240": 3.4405e-5,
        "Pu241": 2.1439e-5,
        "Pu242": 3.7422e-6,
        "Am241": 4.5041e-7,
        "Am242_m1": 9.2301e-9,
        "Am243": 4.7878e-7,
        "Cm242": 1.0485e-7,
        "Cm243": 1.4268e-9,
        "Cm244": 8.8756e-8,
        "Cm245": 3.5285e-9,
        "Mo95": 2.6497e-5,
        "Tc99": 3.2772e-5,
        "Ru101": 3.0742e-5,
        "Ru103": 2.3505e-6,
        "Ag109": 2.0009e-6,
        "Xe135": 1.0801e-8,
        "Cs133": 3.4612e-5,
        "Nd143": 2.6078e-5,
        "Nd145": 1.9898e-5,
        "Sm147": 1.6128e-6,
        "Sm149": 1.1627e-7,
        "Sm150": 7.1727e-6,
        "Sm151": 5.4947e-7,
        "Sm152": 3.0221e-6,
        "Eu153": 2.6209e-6,
        "Gd155": 1.5369e-9,
        "O16": 4.5737e-2,
    }

    # fission products
    fission_products = [
        'Cu65', 'Zn66', 'Zn67', 'Zn68', 'Zn70', 'Ga69', 'Ga71',
        'Ge70', 'Ge72', 'Ge73', 'Ge74', 'Ge76', 'As74', 'As75',
        'Se74', 'Se76', 'Se77', 'Se78', 'Se79', 'Se80', 'Se82',
        'Br79', 'Br81', 'Kr78', 'Kr80', 'Kr82', 'Kr83', 'Kr84',
        'Kr85', 'Kr86', 'Rb85', 'Rb86', 'Rb87', 'Sr84', 'Sr86',
        'Sr87', 'Sr88', 'Sr89', 'Sr90', 'Y89', 'Y90', 'Y91',
        'Zr90', 'Zr91', 'Zr92', 'Zr93', 'Zr94', 'Zr95', 'Zr96',
        'Nb93', 'Nb94', 'Nb95', 'Mo92', 'Mo94', 'Mo96', 'Mo97',
        'Mo98', 'Mo99', 'Mo100', 'Ru96', 'Ru98', 'Ru99', 'Ru100',
        'Ru102', 'Ru104', 'Ru105', 'Ru106', 'Rh103', 'Rh105',
        'Pd102', 'Pd104', 'Pd105', 'Pd106', 'Pd107', 'Pd108', 'Pd110',
        'Ag107', 'Ag110_m1', 'Ag111', 'Cd106', 'Cd108', 'Cd110',
        'Cd111', 'Cd112', 'Cd113', 'Cd114', 'Cd115_m1', 'Cd116',
        'In113', 'In115', 'Sn112', 'Sn113', 'Sn114', 'Sn115', 'Sn116',
        'Sn117', 'Sn118', 'Sn119', 'Sn120', 'Sn122', 'Sn123', 'Sn124',
        'Sn125', 'Sn126', 'Sb121', 'Sb123', 'Sb124', 'Sb125', 'Sb126',
        'Te120', 'Te122', 'Te123', 'Te124', 'Te125', 'Te126', 'Te127_m1',
        'Te128', 'Te129_m1', 'Te130', 'Te132', 'I127', 'I129', 'I130',
        'I131', 'I135', 'Xe124', 'Xe126', 'Xe128', 'Xe129', 'Xe130',
        'Xe131', 'Xe132', 'Xe133', 'Xe134', 'Xe136', 'Cs134', 'Cs135',
        'Cs136', 'Cs137', 'Ba132', 'Ba133', 'Ba134', 'Ba135', 'Ba136',
        'Ba137', 'Ba138', 'Ba140', 'La138', 'La139', 'La140', 'Ce138',
        'Ce139', 'Ce140', 'Ce141', 'Ce142', 'Ce143', 'Ce144', 'Pr141',
        'Pr142', 'Pr143', 'Nd142', 'Nd144', 'Nd146', 'Nd147', 'Nd148',
        'Nd150', 'Pm147', 'Pm148', 'Pm148_m1', 'Pm149', 'Pm151', 'Sm144',
        'Sm148', 'Sm153', 'Sm154', 'Eu151', 'Eu152', 'Eu154', 'Eu155',
        'Eu156', 'Eu157', 'Gd152', 'Gd153', 'Gd154', 'Gd156', 'Gd157',
        'Gd158', 'Gd160', 'Tb159', 'Tb160', 'Dy156', 'Dy158', 'Dy160',
        'Dy161', 'Dy162', 'Dy163', 'Dy164', 'Ho165', 'Ho166_m1',
        'Er162', 'Er164', 'Er166', 'Er167', 'Er168', 'Er170',
        'Tm168', 'Tm169', 'Tm170'
    ]

    # minor actinides
    minor_actinides = ['U233', 'U237', 'Np238', 'Cm246']

    # other reaction products from (n,p), (n,a), etc.
    reaction_products = ['H1', 'H2', 'H3', 'He3', 'He4']

    fuel.add_components(components)
    for nuc in fission_products:
        fuel.add_nuclide(nuc, 1.0e-12)
    for nuc in minor_actinides:
        fuel.add_nuclide(nuc, 1.0e-12)
    for nuc in reaction_products:
        fuel.add_nuclide(nuc, 1.0e-12)

    # Create materials - 10 clones of the fuel material
    materials = openmc.Materials([fuel])
    for i in range(1, 10):
        materials.append(fuel.clone())

    # Create geometry - 10 slab cells with reflective boundaries on outer surfaces
    geometry = openmc.Geometry()

    # Define surfaces for slab boundaries
    zmin = -10.0
    zmax = 10.0
    n = 10

    # generate n+1 plane positions evenly spaced between zmin and zmax
    positions = np.linspace(zmin, zmax, n + 1)
    z_planes = [openmc.ZPlane(z) for z in positions]

    # Set reflective boundary conditions on outer surfaces
    z_planes[0].boundary_type = 'reflective'
    z_planes[-1].boundary_type = 'reflective'

    # Create cells
    cells = []
    for i in range(10):
        region = +z_planes[i] & -z_planes[i + 1]
        cell = openmc.Cell(fill=materials[i], region=region)
        cells.append(cell)
    geometry = openmc.Geometry(cells)

    # Settings with uniform source distribution over the slab
    settings = openmc.Settings()
    settings.batches = 20
    settings.inactive = 10
    settings.particles = 10000

    # Uniform source distribution over the slab (z from zmin to zmax)
    source = openmc.IndependentSource()
    # give the box some small x/y extent and full z extent of the slab
    source.space = openmc.stats.Box([-1.0, -1.0, zmin], [1.0, 1.0, zmax])
    settings.source = source

    return openmc.Model(geometry=geometry, settings=settings)
