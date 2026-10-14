#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
cd "$SCRIPT_DIR"

NETWORK_DIR="${VMT_NETWORK_DIR:-$HOME/vmt-networks}"
OSM_FILE="${OSM_FILE:-$NETWORK_DIR/analysis-area.osm.pbf}"
SPEED_DATABASE="${SPEED_DATABASE:-$SCRIPT_DIR/streetlight_data.db}"
ELEVATION_FILE="${ELEVATION_FILE:-$HOME/Documents/uky_vmt_study/VMT Reduction Mode Shift - General/2-Re-Routing Analysis/Elevation/final.asc}"
SPEED_CAP_DATABASE="${SPEED_CAP_DATABASE:-$NETWORK_DIR/speed_cap_database.db}"
MINNEAPOLIS_2040_GPKG="${MINNEAPOLIS_2040_GPKG:-$HOME/Documents/uky_vmt_study/VMT Reduction Mode Shift - General/Data/GIS/fgdb_society_thrive_msp2040_com_des/society_thrive_msp2040_com_des.gpkg}"
GTFS_FILE_1="${GTFS_FILE_1:-$HOME/Documents/uky_vmt_study/VMT Reduction Mode Shift - General/2-Re-Routing Analysis/GTFS/metro_transit_20230120.zip}"
GTFS_FILE_2="${GTFS_FILE_2:-$HOME/Documents/uky_vmt_study/VMT Reduction Mode Shift - General/2-Re-Routing Analysis/GTFS/mvta-transitfeeds_com-20190903.zip}"

export SPEED_DATABASE ELEVATION_FILE

for command in luarocks sqlite3 osrm-extract osrm-partition osrm-customize julia; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$command" >&2
    exit 1
  fi
done

for input in "$OSM_FILE" "$SPEED_DATABASE" "$ELEVATION_FILE" "$GTFS_FILE_1"; do
  if [[ ! -f "$input" ]]; then
    printf 'Required network-build input not found: %s\n' "$input" >&2
    exit 1
  fi
done

if [[ ! -f "$SPEED_CAP_DATABASE" && ! -f "$MINNEAPOLIS_2040_GPKG" ]]; then
  printf 'Provide SPEED_CAP_DATABASE or MINNEAPOLIS_2040_GPKG to build the car speed scenario\n' >&2
  exit 1
fi

if ! sqlite3 "$SPEED_DATABASE" '.schema stl_congestion_data_2019' | grep 'REAL' >/dev/null; then
  printf 'No REAL-valued StreetLight speed columns found in %s\n' "$SPEED_DATABASE" >&2
  exit 1
fi

eval "$(luarocks path)"

if [[ ! -f "$SPEED_CAP_DATABASE" ]]; then
  printf '\nBuilding speed-cap database from %s\n' "$MINNEAPOLIS_2040_GPKG"
  julia --project="$SCRIPT_DIR" "$SCRIPT_DIR/car_speed_scenario/area_for_way.jl" \
    "$OSM_FILE" "$MINNEAPOLIS_2040_GPKG" "$SPEED_CAP_DATABASE"
fi

run_builder() {
  local builder="$1"
  shift
  printf '\nBuilding with %s\n' "$builder"
  bash -euo pipefail "$SCRIPT_DIR/$builder" "$@"
}

SPEED_COLUMN=saturdays_6-7 BIKE_SCENARIO=baseline run_builder _build_street_network.sh \
  "$OSM_FILE" "$SCRIPT_DIR/profiles/bicycle_lts.lua" "$NETWORK_DIR/bike-lts"
SPEED_COLUMN=saturdays_6-7 run_builder _build_street_network.sh \
  "$OSM_FILE" "$SCRIPT_DIR/profiles/foot_lts.lua" "$NETWORK_DIR/foot-lts"

run_builder build_walk_baseline_network.sh "$OSM_FILE" "$NETWORK_DIR"
run_builder build_walk_scenario_network.sh "$OSM_FILE" "$NETWORK_DIR"
run_builder build_bicycle_baseline_network.sh "$OSM_FILE" "$NETWORK_DIR"
run_builder build_bicycle_ebike_network.sh "$OSM_FILE" "$NETWORK_DIR"
run_builder build_bicycle_all_lts1_network.sh "$OSM_FILE" "$NETWORK_DIR"
run_builder build_car_baseline_networks.sh "$OSM_FILE" "$NETWORK_DIR"

run_builder build_transit_network.sh \
  --osrm-network "$NETWORK_DIR/walk-baseline/walk-baseline.osrm" \
  -t 2413.5 \
  "$NETWORK_DIR/transit.trjl" \
  "$GTFS_FILE_1" \
  "$GTFS_FILE_2"

run_builder convert_all_networks_to_gis.sh "$NETWORK_DIR"