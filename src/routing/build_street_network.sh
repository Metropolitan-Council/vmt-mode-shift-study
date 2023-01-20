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

ln -s "${OSM_FILE}" "${OSM_TARGET}"
osrm-extract -p "${PROFILE}" "${OSM_TARGET}"
osrm-partition "${OSRM_TARGET}"
osrm-customize "${OSRM_TARGET}"
