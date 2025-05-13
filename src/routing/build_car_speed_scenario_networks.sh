#!/bin/bash
# This encapsulates the network build options for the car traffic baseline networks.
# The only arguments it takes are the path to the OSM file, and the output directory; a bike-lts
# directory will be created within it. It still expects SPEED_DATABASE to be set in the environment.

set -ex

OSM="$1"
OUTDIR="$2"

PROFILE="$(dirname "$0")/profiles/car_traffic.lua"

# make sure we don't accidentally cap speeds
SPEED_CAP_DB="$3"

# use an SQL query to get all of the speed columns, then use xargs to build a network
# for each one
echo ".schema stl_congestion_data_2019" |
    sqlite3 "$SPEED_DATABASE" |
    grep REAL |
    sed -E 's/^ +"([^"]+).*$/\1/' | 
    xargs -Icol env SPEED_COLUMN=col SPEED_CAP_DATABASE="$SPEED_CAP_DB" bash "$(dirname "$0")/_build_street_network.sh" "$OSM" "$PROFILE" "${OUTDIR}/car_scenario_col"

