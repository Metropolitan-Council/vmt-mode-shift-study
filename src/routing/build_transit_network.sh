#!/bin/bash

# command used for scenario network: bash build_transit_network.sh --osrm-network ~/vmt-networks/walk-lts/walk-lts.osrm \
#  -t 2413.5 ~/vmt-networks/transit-scenario.trjl \
# /mnt/c/Users/mwbc/University\ of\ Kentucky/VMT\ Reduction\ Mode\ Shift\ -\ General/2-Re-Routing\ Analysis/GTFS/metro_transit_2019-10-16-scenario.zip \
# /mnt/c/Users/mwbc/University\ of\ Kentucky/VMT\ Reduction\ Mode\ Shift\ -\ General/2-Re-Routing\ Analysis/GTFS/mvta-scenario.zip

set -ex

# may be relative path but that's ok
export JULIA_PROJECT="$(dirname \"${0}\")"

# unfortunately julia doesn't have a great way to get the path of a package, hack something together
SCRIPT_PATH="$(julia << EOF
using TransitRouter
println(joinpath(dirname(dirname(pathof(TransitRouter))), "build_network.jl"))
EOF
)"

julia -t auto "${SCRIPT_PATH}" "$@"