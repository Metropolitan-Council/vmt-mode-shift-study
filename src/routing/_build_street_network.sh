#!/bin/bash
# Build the OSRM network based on an OSM file, a profile, and an output directory.
# This generally should not be used directly, but rather called from one of the build_*_network.sh
# scripts which encapsulate the settings needed for any particular network.
set -euo pipefail
set -x

if [[ "$#" -ne 3 ]]; then
	printf 'Usage: %s OSM_FILE PROFILE OUTPUT_DIR\n' "$0" >&2
	exit 2
fi

OSM_FILE="$1"
PROFILE="$2"
OUTPUT_DIR="${3%/}"

if [[ -z "$OUTPUT_DIR" ]]; then
	printf 'OUTPUT_DIR must be a network-specific directory\n' >&2
	exit 2
fi

if [[ ! -f "$OSM_FILE" ]]; then
	printf 'OSM input not found: %s\n' "$OSM_FILE" >&2
	exit 1
fi

if [[ ! -r "$PROFILE" ]]; then
	printf 'Profile is not readable: %s\n' "$PROFILE" >&2
	exit 1
fi

OUTPUT_NAME="$(basename "$OUTPUT_DIR")"
if [[ "$OUTPUT_NAME" == "." || "$OUTPUT_NAME" == ".." ]]; then
	printf 'OUTPUT_DIR must name a network-specific directory\n' >&2
	exit 2
fi

OUTPUT_PARENT="$(cd "$(dirname "$OUTPUT_DIR")" && pwd -P)"
OUTPUT_DIR="${OUTPUT_PARENT}/${OUTPUT_NAME}"
NET_NAME="$OUTPUT_NAME"

if [[ "$OUTPUT_DIR" == "/" || "$OUTPUT_DIR" == "$HOME" || "$OUTPUT_DIR" == "$HOME/vmt-networks" ]]; then
	printf 'Refusing to replace non-network directory: %s\n' "$OUTPUT_DIR" >&2
	exit 2
fi

if [[ -e "$OUTPUT_DIR" && ! -d "$OUTPUT_DIR" ]]; then
	printf 'Output path is not a directory: %s\n' "$OUTPUT_DIR" >&2
	exit 1
fi

if [[ -d "$OUTPUT_DIR" ]]; then
	for OUTPUT_ENTRY in "$OUTPUT_DIR"/* "$OUTPUT_DIR"/.[!.]* "$OUTPUT_DIR"/..?*; do
		[[ -e "$OUTPUT_ENTRY" || -L "$OUTPUT_ENTRY" ]] || continue
		ENTRY_NAME="$(basename "$OUTPUT_ENTRY")"
		case "$ENTRY_NAME" in
			"${NET_NAME}.osm.pbf"|"${NET_NAME}.osrm"|"${NET_NAME}.osrm."*)
				if [[ -d "$OUTPUT_ENTRY" && ! -L "$OUTPUT_ENTRY" ]]; then
					printf 'Refusing to replace nested directory in network output: %s\n' "$OUTPUT_ENTRY" >&2
					exit 1
				fi
				;;
			*)
				printf 'Refusing to replace unrecognized output: %s\n' "$OUTPUT_ENTRY" >&2
				exit 1
				;;
		esac
	done
	rm -rf "$OUTPUT_DIR"
fi

mkdir "$OUTPUT_DIR"

OSM_TARGET="${OUTPUT_DIR}/${NET_NAME}.osm.pbf"
OSRM_TARGET="${OSM_TARGET%.osm.pbf}.osrm"
# Resolve the parent directory to an absolute path; macOS readlink lacks the -f option.
OSM_FULL_PATH="$(cd "$(dirname "$OSM_FILE")" && pwd -P)/$(basename "$OSM_FILE")"

ln -s "${OSM_FULL_PATH}" "${OSM_TARGET}"
osrm-extract -p "${PROFILE}" "${OSM_TARGET}" 2>&1 |
	sed \
		-e '/\[source loader\] Already loaded source .* at source_id [0-9][0-9]*$/d' \
		-e '/\[info\] Using profile api version [0-9][0-9]*$/d'
osrm-partition "${OSRM_TARGET}"
osrm-customize "${OSRM_TARGET}"
