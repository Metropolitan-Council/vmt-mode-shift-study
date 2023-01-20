#!/bin/bash
set -ex

# may be relative path but that's ok
export JULIA_PROJECT="$(dirname \"${0}\")"

# unfortunately julia doesn't have a great way to get the path of a package, hack something together
SCRIPT_PATH="$(julia << EOF
using TransitRouter
println(joinpath(dirname(dirname(pathof(TransitRouter))), "build_network.jl"))
EOF
)"

julia "${SCRIPT_PATH}" "$@"