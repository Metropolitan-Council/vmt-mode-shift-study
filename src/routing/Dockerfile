# This dockerfile creates a container that has Julia, OSRM, and the requisite packages for doing
# street and transit routing. It is tested using Podman but should work with Docker as well.

# To build the image, in the src/routing directory run docker build . -t vmt-routing
# If you're using Podman, andthe build is slow or fails with message like "cc1plus: killed," you may
# need to increase the memory and number of CPUs available to Podman with something like:
#   podman machine stop
#   podman machine set --cpus 8 --memory 8192
#   podman machine start

# Start with official Docker Julia image, on Debian bookworm
FROM julia:1.9.4-bookworm

##############
# Build OSRM #
##############

# Install OSRM dependencies
RUN apt-get update; apt-get install -y clang build-essential unzip cmake pkg-config \
    libbz2-dev libstxxl-dev libstxxl1v5 libxml2-dev \
    libzip-dev libboost-all-dev lua5.4 liblua5.4-dev libtbb-dev

# Building with GCC 12 does not work as of yet, use clang
# https://github.com/Project-OSRM/osrm-backend/issues/6704
ENV CXX=clang++
ENV CC=clang

# currently we have to build off a branch of OSRM, until https://github.com/Project-OSRM/osrm-backend/pull/6658
# is merged.
RUN (curl -L -o osrm.zip https://codeload.github.com/mattwigway/osrm-backend/zip/refs/heads/process-segment-flags && \
    unzip osrm.zip && \
    cd osrm-backend-process-segment-flags && \
    #patch < ../osrm-array-bounds.patch && \
    mkdir build && \
    cd build && \
    cmake -DBUILD_SHARED_LIBS=ON .. && \
    cmake --build . -j8 && \
    cmake --build . --target install && \
    cd ../.. && \
    rm -rf osrm-backend-process-segment-flags &&\
    rm osrm.zip)

###########################
# Setup Julia environment #
###########################

# We install all required Julia packages into the global environment in the container. We do
# not need separate Julia environments, since the container is only used for routing.

RUN echo foo
COPY Manifest.toml /root/.julia/environments/v1.9/Manifest.toml

# OSRM.jl is not currently available in the Julia General registry, because the OSRM binary is not
# packaged as part of the Julia package manager yet.  
RUN julia -e 'using Pkg; Pkg.Registry.add("General"); Pkg.Registry.add(RegistrySpec(url="https://github.com/mattwigway/PublicJuliaRegistry.git")); Pkg.instantiate()'

##########################
# Install Julia C++ shim #
##########################

# This C++ shim enables OSRM.jl to call OSRM. We make sure we are using the shim that goes with the version of OSRM.jl in use
# by using the source within the Julia installation directory.
RUN cd "$(julia -e 'import OSRM; print(dirname(dirname(pathof(OSRM))))')/cxx" && \
    mkdir build && \
    cd build && \
    cmake .. && \
    cmake --build . && \
    cmake --build . --target install

ENTRYPOINT [ "/bin/bash", "-c" ]
CMD [ "bash" ]