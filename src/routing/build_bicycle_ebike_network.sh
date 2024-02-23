#!/bin/bash
# This encapsulates the network build options for the bicycle e-bike scenario network.
# The only arguments it takes are the path to the OSM file, and the output directory; a bike-lts
# directory will be created within it. It still expects ELEVATION_FILE and SPEED_DATABASE to be set in the environment.

set -ex

OSM="$1"
OUTDIR="$2"

PROFILE="$(dirname "$0")/profiles/bicycle_lts.lua"

export SPEED_COLUMN="saturdays_6-7"
export BIKE_SCENARIO="e-bike"

bash build_street_network.sh "$OSM" "$PROFILE" "${OUTDIR}/bike-ebike"