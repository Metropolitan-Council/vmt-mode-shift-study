# Convert all the network files to GIS format

NET_DIR="$1"
SOURCE_DIR="$(dirname "$0")"

set -e

for dir in "$NET_DIR/"*; do
    netname="$(basename "$dir")" 
    echo "Converting $netname"
    if [ -d "$dir" -a -e "${dir}/${netname}.osrm.ebg" ]; then
        julia "${SOURCE_DIR}/network_to_gis.jl" "${dir}/${netname}.osrm" "${dir}/${netname}.gpkg"
    fi
done