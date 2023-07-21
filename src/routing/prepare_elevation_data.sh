#!/bin/bash
# Merge the elevation data together, and reproject to match OSM
set -ex

DIR=$1

gdal_merge.py -o "$DIR/combined.tif" -of GTIFF "$DIR/USGS_"*.tif

# convert elevation to millimeters, avoid roundoff error
# 1 mm is surely far more than the vertical resolution of the file, but it allows smoother interpolation
gdal_calc.py --calc "A*1000" -A "$DIR/combined.tif" --outfile "$DIR/millimeters.tif"


# reproject to WGS 84 to match OSM
# use bilinear, since most targets will be very close to the original
gdalwarp -t_srs "+init=EPSG:4326" -r bilinear -of AAIGRID -ot Int32 "$DIR/millimeters.tif" "$DIR/final_esri.asc"

head -n 6 final_esri.asc > final_header.asc
tail -n +7 final_esri.asc > final.asc