#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROUTING_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"

usage() {
	printf 'Usage: %s [NETWORK_DIR [ELEVATION_TIF [STREETLIGHT_DB [SPEED_COLUMN [SPEED_CAP_DB]]]]]\n' "$0" >&2
}

if [[ "$#" -gt 5 ]]; then
	usage
	exit 2
fi

NETWORK_DIR="${1:-${VMT_NETWORK_DIR:-$HOME/vmt-networks}}"
BUILD_ELEVATION_FILE="${ELEVATION_FILE:-$HOME/Documents/uky_vmt_study/VMT Reduction Mode Shift - General/2-Re-Routing Analysis/Elevation/final.asc}"
DEFAULT_ELEVATION_TIF="$(dirname "$BUILD_ELEVATION_FILE")/combined.tif"
if [[ "$BUILD_ELEVATION_FILE" == *.tif ]]; then
	DEFAULT_ELEVATION_TIF="$BUILD_ELEVATION_FILE"
fi
ELEVATION_FILE="${2:-$DEFAULT_ELEVATION_TIF}"
SPEED_DATABASE="${3:-${SPEED_DATABASE:-$ROUTING_DIR/streetlight_data.db}}"
SPEED_COLUMN="${4:-${SPEED_COLUMN:-weekdays_7-8}}"
SPEED_CAP_DATABASE="${5:-${SPEED_CAP_DATABASE:-}}"

if ! command -v julia >/dev/null 2>&1; then
	printf 'Required command not found: julia\n' >&2
	exit 1
fi

require_file() {
	if [[ ! -r "$1" ]]; then
		printf 'Required input not found or not readable: %s\n' "$1" >&2
		exit 1
	fi
}

require_network() {
	local network_prefix="$1"
	if [[ ! -r "${network_prefix}.ebg" ]]; then
		printf 'OSRM network files not found for: %s\n' "$network_prefix" >&2
		exit 1
	fi
}

if [[ ! -d "$NETWORK_DIR" ]]; then
	printf 'Network directory not found: %s\n' "$NETWORK_DIR" >&2
	exit 1
fi

BIKE_NETWORK="$NETWORK_DIR/bike-baseline/bike-baseline.osrm"
WALK_NETWORK="$NETWORK_DIR/walk-baseline/walk-baseline.osrm"
CAR_NETWORK="$NETWORK_DIR/car_baseline_$SPEED_COLUMN/car_baseline_$SPEED_COLUMN.osrm"

require_network "$BIKE_NETWORK"
require_network "$WALK_NETWORK"
require_network "$CAR_NETWORK"
require_file "$ELEVATION_FILE"
require_file "$SPEED_DATABASE"
if [[ -n "$SPEED_CAP_DATABASE" ]]; then
	require_file "$SPEED_CAP_DATABASE"
fi

failed_tests=()
run_test() {
	local test_name="$1"
	shift
	printf '\nRunning %s tests\n' "$test_name"
	if "$@"; then
		printf '%s tests passed\n' "$test_name"
	else
		local exit_code="$?"
		printf '%s tests failed with exit code %s; continuing\n' "$test_name" "$exit_code" >&2
		failed_tests+=("$test_name")
	fi
}

run_test bicycle julia --project="$ROUTING_DIR" "$SCRIPT_DIR/test_bicycle.jl" "$BIKE_NETWORK" "$ELEVATION_FILE"
run_test pedestrian julia --project="$ROUTING_DIR" "$SCRIPT_DIR/test_ped_baseline.jl" "$WALK_NETWORK" "$ELEVATION_FILE"

if [[ -n "$SPEED_CAP_DATABASE" ]]; then
	run_test car julia --project="$ROUTING_DIR" "$SCRIPT_DIR/test_car_traffic.jl" \
		"$CAR_NETWORK" "$SPEED_DATABASE" "$SPEED_COLUMN" --nacto-cap "$SPEED_CAP_DATABASE"
else
	run_test car julia --project="$ROUTING_DIR" "$SCRIPT_DIR/test_car_traffic.jl" \
		"$CAR_NETWORK" "$SPEED_DATABASE" "$SPEED_COLUMN"
fi

if [[ "${#failed_tests[@]}" -gt 0 ]]; then
	printf '\nFailed test scripts: %s\n' "${failed_tests[*]}" >&2
	exit 1
fi

printf '\nAll network test scripts passed\n'