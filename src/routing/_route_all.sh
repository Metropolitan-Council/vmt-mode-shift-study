#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
cd "$SCRIPT_DIR"


if [[ "$#" -gt 3 ]]; then
    printf 'Usage: %s [TBI_DIR [NET_DIR [OUT_DIR]]]\n' "$0" >&2
    exit 2
fi

TBI_DIR="${1:-${TBI_DIR:-$SCRIPT_DIR/../../data_processing}}"
NET_DIR="${2:-${VMT_NETWORK_DIR:-$HOME/vmt-networks}}"
OUT_DIR="${3:-${VMT_OUT_DIR:-$HOME/vmt-routing}}"

TBI_DIR="$(cd "$TBI_DIR" && pwd -P)"
NET_DIR="$(cd "$NET_DIR" && pwd -P)"
mkdir -p "$OUT_DIR"

OUT_DIR="$(cd "$OUT_DIR" && pwd -P)"

if [[ ! -f "$TBI_DIR/tbi_cleaned.csv" ]]; then
    printf 'TBI input not found: %s/tbi_cleaned.csv\n' "$TBI_DIR" >&2
    exit 1
fi

for network in walk-baseline walk-scenario bike-baseline bike-ebike bike-all-lts1; do
    if [[ ! -d "$NET_DIR/$network" ]]; then
        printf 'Required network directory not found: %s/%s\n' "$NET_DIR" "$network" >&2
        exit 1
    fi
done

shopt -s nullglob
car_baseline_networks=("$NET_DIR"/car_baseline_*/)
car_scenario_networks=("$NET_DIR"/car_scenario_*/)
if [[ "${#car_baseline_networks[@]}" -eq 0 || "${#car_scenario_networks[@]}" -eq 0 ]]; then
    printf 'Car baseline and scenario networks must exist under %s\n' "$NET_DIR" >&2
    exit 1
fi

if [[ ! -f "$NET_DIR/transit.trjl" ]]; then
    printf 'Transit network not found: %s/transit.trjl\n' "$NET_DIR" >&2
    exit 1
fi

for command in git julia; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$command" >&2
        exit 1
    fi
done

cd "$SCRIPT_DIR"
export JULIA_PROJECT="$SCRIPT_DIR"

run_route_wrapper() {
    local wrapper="$1"
    printf '\nRouting with %s\n' "$wrapper"
    bash -euo pipefail "$SCRIPT_DIR/$wrapper" "$TBI_DIR" "$NET_DIR" "$OUT_DIR"
}

run_route_wrapper route_walk_baseline.sh
run_route_wrapper route_walk_scenario.sh
run_route_wrapper route_bicycle_baseline.sh
run_route_wrapper route_bicycle_ebike.sh
run_route_wrapper route_bicycle_all_lts1.sh
run_route_wrapper route_car_congestion.sh
run_route_wrapper route_car_speed_scenario.sh

COMMIT_HASH="$(git rev-parse --short=5 HEAD)"
TRANSIT_OUTPUT="$OUT_DIR/transit-${COMMIT_HASH}.parquet"


if [[ -e "$TRANSIT_OUTPUT" ]]; then
    printf 'Transit output already exists: %s\n' "$TRANSIT_OUTPUT"
else
    julia -t auto "$SCRIPT_DIR/route.jl" \
        --transit-network "$NET_DIR/transit.trjl" \
        "$TBI_DIR/tbi_cleaned.csv" \
        "$NET_DIR/walk-baseline/walk-baseline.osrm" \
        "$TRANSIT_OUTPUT"
fi