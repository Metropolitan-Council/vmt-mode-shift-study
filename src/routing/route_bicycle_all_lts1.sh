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

OUT_FILE="${OUT_DIR}/bike-all-lts1-${COMMIT_HASH}.parquet"
SEGMENTS_FILE="${OUT_DIR}/bike-all-lts1-${COMMIT_HASH}-segments.parquet"

if [ -e "$OUT_FILE" -o -e "$SEGMENTS_FILE" ]; then
    echo "Output files already exist!"
else
    julia --project="$routing" -t auto "${routing}/route.jl" "${TBI_DIR}/tbi_cleaned.csv" "${NET_DIR}/bike-all-lts1/bike-all-lts1.osrm" "$OUT_FILE" --bike-lts "$SEGMENTS_FILE"
fi
