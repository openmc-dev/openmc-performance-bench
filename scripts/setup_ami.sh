#!/bin/bash

set -e

# Install apt dependencies
sudo apt update -y
sudo apt upgrade -y
sudo apt install -y \
     python3-pip python3-venv python-is-python3 build-essential \
     cmake gfortran g++ libpugixml-dev libpng-dev libfmt-dev libhdf5-dev  \
     libeigen3-dev libnetcdf-dev libtbb-dev libglfw3-dev libembree-dev m4 \
     libmpich-dev

# Create and activate Python virtual environment
mkdir venv
python -m venv venv/openmc_env
source venv/openmc_env/bin/activate
python -m pip install -U pip
python -m pip install wheel

MOAB_INSTALL_DIR=$HOME/software/moab
DD_INSTALL_DIR=$HOME/software/double-down
DAGMC_INSTALL_DIR=$HOME/software/dagmc
LIBMESH_INSTALL_DIR=$HOME/software/libmesh
NJOY_INSTALL_DIR=$HOME/software/njoy2016
OPENMC_INSTALL_DIR=$HOME/software/openmc

# Install NJOY
git clone --single-branch --depth 1 https://github.com/njoy/NJOY2016
pushd NJOY2016
mkdir build && pushd build
cmake -Dstatic=on \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_INSTALL_PREFIX=$NJOY_INSTALL_DIR \
      ..
make 2>/dev/null -j2 install
popd && popd
rm -rf $HOME/NJOY2016

# Clone and install MOAB
python -m pip install -U numpy cython setuptools
git clone  --single-branch -b 5.5.1 --depth 1 https://bitbucket.org/fathomteam/moab
pushd moab
mkdir build && pushd build
cmake -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=$MOAB_INSTALL_DIR \
      -DBUILD_SHARED_LIBS=ON \
      -DENABLE_HDF5=ON \
      -DENABLE_NETCDF=ON \
      -DENABLE_FORTRAN=OFF \
      -DENABLE_BLASLAPACK=OFF \
      -DENABLE_PYMOAB=ON \
      -DPython_FIND_UNVERSIONED_NAMES=FIRST \
      ..
make -j2 install
popd && popd
rm -rf $HOME/moab

# Clone and install Double-Down
git clone https://github.com/pshriwise/double-down
pushd double-down
mkdir build && pushd build
cmake -DCMAKE_INSTALL_PREFIX=$DD_INSTALL_DIR \
      -DMOAB_DIR=$MOAB_INSTALL_DIR \
      -DEMBREE_DIR=/usr \
      ..
make 2>/dev/null -j2 install
popd && popd
rm -rf $HOME/double-down

# Clone and install DAGMC
git clone --single-branch -b v3.2.4 --depth 1 https://github.com/svalinn/DAGMC
pushd DAGMC
mkdir build && pushd build
cmake -DCMAKE_INSTALL_PREFIX=$DAGMC_INSTALL_DIR \
      -DCMAKE_PREFIX_PATH=$DD_INSTALL_DIR/lib \
      -DBUILD_TALLY=ON \
      -DBUILD_STATIC_LIBS=OFF \
      -DBUILD_RPATH=ON \
      -DMOAB_DIR=$MOAB_INSTALL_DIR \
      -DDOUBLE_DOWN=ON \
      -DDOUBLE_DOWN_DIR=$DD_INSTALL_DIR \
      ..
make 2>/dev/null -j2 install
popd && popd
rm -fr $HOME/DAGMC

# Clone and install libMesh
git clone https://github.com/libmesh/libmesh -b v1.7.1 --recurse-submodules
mv gklib_fix.patch libmesh/
pushd libmesh
patch -p1 < gklib_fix.patch
mkdir build && pushd build
export METHODS="opt"
../configure --prefix=$LIBMESH_INSTALL_DIR --enable-exodus --disable-netcdf-4 --disable-eigen --disable-lapack --disable-mpi
make -j2 install
popd && popd
rm -rf $HOME/libmesh

# Download and set cross section data
mkdir $HOME/data
pushd data
wget --content-disposition https://anl.box.com/shared/static/9igk353zpy8fn9ttvtrqgzvw1vtejoz6.xz
tar xvf endfb71.tar.xz
rm endfb71.tar.xz
popd

# Set environment variables in .profile
cat >> $HOME/.profile <<EOF
export PATH=\$HOME/openmc/build/bin:$DAGMC_INSTALL_DIR/bin:$MOAB_INSTALL_DIR/bin:$NJOY_INSTALL_DIR/bin:\$PATH
export OPENMC_CROSS_SECTIONS=\$HOME/data/endfb-vii.1-hdf5/cross_sections.xml
EOF

# Add 'source venv' in .bashrc
cat >> $HOME/.bashrc <<EOF
source \$HOME/venv/openmc_env/bin/activate
EOF
