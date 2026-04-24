#!/usr/bin/env bash
set -euxo pipefail

# Adjust if needed
PYVER=3.12
TOOLS_VENV=/opt/tools-venv
OPENMC_DATA_DIR=/opt/data
OPENMC_SOFTWARE_DIR=/opt/software

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# Core toolchain + OpenMC prerequisites + benchmarking utilities
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  build-essential g++ gfortran cmake git wget jq \
  python${PYVER} python${PYVER}-venv python${PYVER}-dev python3-pip \
  openmpi-bin libopenmpi-dev libhdf5-openmpi-dev libpng-dev libpugixml-dev \
  libfmt-dev libeigen3-dev libnetcdf-dev libtbb-dev numactl libembree-dev time

sudo mkdir -p ${TOOLS_VENV}
sudo chown ubuntu:ubuntu ${TOOLS_VENV}

# Create tooling virtual environment
python${PYVER} -m venv ${TOOLS_VENV}
source ${TOOLS_VENV}/bin/activate
python${PYVER} -m pip install --upgrade pip setuptools wheel
python${PYVER} -m pip install asv virtualenv
deactivate

MOAB_INSTALL_DIR=${OPENMC_SOFTWARE_DIR}/moab
DD_INSTALL_DIR=${OPENMC_SOFTWARE_DIR}/double-down
DAGMC_INSTALL_DIR=${OPENMC_SOFTWARE_DIR}/dagmc

sudo mkdir -p "${OPENMC_SOFTWARE_DIR}"
sudo chown ubuntu:ubuntu "${OPENMC_SOFTWARE_DIR}"

# Clone and install MOAB
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
      -DENABLE_PYMOAB=OFF \
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
make -j2 install
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
make -j2 install
popd && popd
rm -fr $HOME/DAGMC

# Download and set cross section data
sudo mkdir -p "${OPENMC_DATA_DIR}"
sudo chown ubuntu:ubuntu "${OPENMC_DATA_DIR}"
cd "${OPENMC_DATA_DIR}"
wget --content-disposition https://anl.box.com/shared/static/9igk353zpy8fn9ttvtrqgzvw1vtejoz6.xz
tar xvf endfb71.tar.xz
rm endfb71.tar.xz
cd "${HOME}"

echo
echo "Provisioning complete."
echo "Cross sections are at:"
echo "  ${OPENMC_DATA_DIR}/endfb-vii.1-hdf5/cross_sections.xml"
echo
echo "Sanity checks:"
python${PYVER} --version
cmake --version
mpirun --version
h5pcc -showconfig || h5cc -showconfig || true
${TOOLS_VENV}/bin/asv --version
${TOOLS_VENV}/bin/python -m pip show asv

# Clean up instance
sudo apt-get clean
sudo apt-get autoremove -y
sudo rm -rf /tmp/* /var/tmp/*
rm -rf ~/.cache/* ~/.bash_history
sudo rm -rf /root/.cache/* /root/.bash_history
