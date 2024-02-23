# This dockerfile creates a container that has Julia, OSRM, and the requisite packages for doing
# street and transit routing. It is tested using Podman but should work with Docker as well.

# To build the image, in the src/routing directory run docker build . -t vmt-routing
# If you're using Podman on a mac, and the build is slow or fails with message like "cc1plus: killed," you may
# need to increase the memory and number of CPUs available to Podman with something like:
#   podman machine stop
#   podman machine set --cpus 8 --memory 8192
#   podman machine start

# Start with official Docker Julia image, on Debian bookworm
FROM julia:1.10.0-bookworm

##############
# Build OSRM #
##############

# Install OSRM dependencies
# luarocks Debian package currently not compatible with lua 5.4, use lua 5.3 for this reason
# luarocks is needed to install lua lsqlite3 package
RUN apt-get update
RUN apt-get install -y clang build-essential unzip cmake pkg-config \
    libbz2-dev libstxxl-dev libstxxl1v5 libxml2-dev \
    libzip-dev libboost-all-dev lua5.3 liblua5.3-dev libtbb-dev \
    sqlite3 libsqlite3-dev luarocks git tmux

# Building OSRM with GCC 12 does not work as of yet, use clang
# https://github.com/Project-OSRM/osrm-backend/issues/6704
ENV CXX=clang++
ENV CC=clang

RUN luarocks install lsqlite3

# We want to run Julia etc as a non-privileged user for security
RUN useradd -mU vmt
USER vmt

# currently we have to build off a branch of OSRM, until https://github.com/Project-OSRM/osrm-backend/pull/6658
# is merged.
RUN cd &&\
    curl -L -o osrm.zip https://codeload.github.com/mattwigway/osrm-backend/zip/refs/heads/process-segment-flags && \
    unzip osrm.zip && \
    cd osrm-backend-process-segment-flags && \
    #patch < ../osrm-array-bounds.patch && \
    mkdir build && \
    cd build && \
    cmake -DBUILD_SHARED_LIBS=ON .. && \
    cmake --build . -j8
USER root
RUN cd ~vmt/osrm-backend-process-segment-flags/build && cmake --build . --target install
USER vmt
RUN cd && \
    rm -rf osrm-backend-process-segment-flags &&\
    rm osrm.zip

###########################
# Setup Julia environment #
###########################

# We install all required Julia packages into the global environment in the container. We do
# not need separate Julia environments, since the container is only used for routing.

COPY --chown=vmt:vmt Manifest.toml /home/vmt/.julia/environments/v1.10/Manifest.toml

# OSRM.jl is not currently available in the Julia General registry, because the OSRM binary is not
# packaged as part of the Julia package manager yet.  
RUN julia -e 'using Pkg; Pkg.Registry.add("General"); Pkg.Registry.add(RegistrySpec(url="https://github.com/mattwigway/PublicJuliaRegistry.git")); Pkg.instantiate()'

##########################
# Install Julia C++ shim #
##########################

# This C++ shim enables OSRM.jl to call OSRM. We make sure we are using the shim that goes with the version of OSRM.jl in use
# by using the source within the Julia installation directory.
# Store the directory so we can access when it comes time to make install
RUN julia -e 'import OSRM; print(joinpath(dirname(dirname(pathof(OSRM))), "cxx"))' > ~vmt/cxxloc.txt
RUN cd "$(cat ~vmt/cxxloc.txt)" && \
    mkdir build && \
    cd build && \
    cmake .. && \
    cmake --build .
USER root
RUN cd "$(cat ~vmt/cxxloc.txt)/build" && cmake --build . --target install
RUN rm ~vmt/cxxloc.txt

###############################
# Rebuild shared library path #
###############################

# This is needed so that the osrm-* executables can find the relevant OSRM shared libraries
RUN ldconfig

USER vmt
WORKDIR /home/vmt

ENTRYPOINT [ "/bin/bash", "-c" ]
CMD [ "bash" ]