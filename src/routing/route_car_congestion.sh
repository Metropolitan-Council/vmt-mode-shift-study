#!/bin/bash
# This encapsulates the routing options for the bicycle All LTS 1 scenario. It takes arguments for the path where the TBI is stored,
# directory where all the networks are stored,
# and the directory where output should go.

set -ex

TBI_DIR="$1"
NET_DIR="$2"
OUT_DIR="$3"

routing="$(dirname "$0")"

# get the git commit hash
COMMIT_HASH=$(cd "$routing"; git rev-parse HEAD | head -c 5)

for netdir in "${NET_DIR}/car_congestion*/"; do
    netname="$(basename "$net")"
    echo $netname
    OUT_FILE="${OUT_DIR}/${netname}-${COMMIT_HASH}.parquet"
    NET_BASE="${NET_DIR}/${netname}/${netname}.osrm"

    if [ -e "$OUT_FILE" ]; then
        echo "Output files already exist!"
    else
        # Note: when running locally, add --project="$routing" after julia
        julia -t auto "${routing}/route.jl" "${TBI_DIR}/tbi_cleaned.csv" "$NET_BASE" "$OUT_FILE"
    fi
done
