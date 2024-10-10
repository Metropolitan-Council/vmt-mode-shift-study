#!/bin/bash
# Build the OSRM network based on an OSM file, a profile, and an output directory
set -ex

OSM_FILE="${1}"
PROFILE="${2}"
OUTPUT_DIR="${3}"

mkdir "${OUTPUT_DIR}"

NET_NAME=`basename ${OUTPUT_DIR}`
OSM_TARGET="${OUTPUT_DIR}/${NET_NAME}.osm.pbf"
OSRM_TARGET="${OSM_TARGET%.osm.pbf}.osrm"
# use readlink to get the absolute path, to avoid differences between macOS and Linux when
# creating symlinks to a relative path in a subdirectory.
OSM_FULL_PATH="$(readlink -f "${OSM_FILE}")"

ln -s "${OSM_FULL_PATH}" "${OSM_TARGET}"
osrm-extract -p "${PROFILE}" "${OSM_TARGET}"
osrm-partition "${OSRM_TARGET}"
osrm-customize "${OSRM_TARGET}"
