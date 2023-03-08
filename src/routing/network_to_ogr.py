# This converts an OSRM network to a GeoPackage (or other multi-layer OGR file)
# It uses the vector tile API from OSRM, so osrm-routed needs to be running. You
# then run the script like so:
#  network_to_ogr.py http://localhost:5000 min_lon min_lat max_lon max_lat output.gpkg
# and the network will be written to output.gpkg.

# output.gpkg will have three layers: speeds, osmnodes, and turns. Speeds are the links in the network,
# with attributes about their weight and duration. osmnodes are the original OSM nodes. Turns represent
# the weights for turns. Because the data is extracted from a tile API, there will be occasional places where
# a single graph edge is split into two in the tiles (the weight and duration are not adjusted for the splitting,
# both features will have the weight and duration of the original edge)

# ogr2ogr >= 2.3 needs to be installed for this script to work.

import requests
from tqdm import tqdm
import math
import argparse
import os
import tempfile
import itertools
import logging as LOG
import json
import subprocess

# from https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Lon./lat._to_tile_numbers
def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

parser = argparse.ArgumentParser(prog="network_to_geopackage", description="convert an OSRM network to GeoPackage format")

parser.add_argument("server")
parser.add_argument("min_lon")
parser.add_argument("min_lat")
parser.add_argument("max_lon")
parser.add_argument("max_lat")
parser.add_argument("output")

args = parser.parse_args()

zoom = 16
# find corners
tl = deg2num(float(args.max_lat), float(args.min_lon), zoom)
br = deg2num(float(args.min_lat), float(args.max_lon), zoom)

all_tiles = list(itertools.product(range(tl[0], br[0] + 1), range(tl[1], br[1] + 1)))

# Create a temporary directory to store our downloaded tiles
data = None
with tempfile.TemporaryDirectory() as tempdir:
    tiledir = os.path.join(tempdir, "tiles")
    os.mkdir(tiledir)
    zdir = os.path.join(tiledir, f"{zoom}")
    os.mkdir(zdir)
    for x in range(tl[0], br[0] + 1):
        os.mkdir(os.path.join(zdir, f"{x}"))
    
    LOG.info("Downloading tiles")
    for x, y in tqdm(all_tiles):
        # fetch the tile
        res = requests.get(f"{args.server}/tile/v1/profile/tile({x},{y},{zoom}).mvt")
        with open(os.path.join(zdir, f"{x}", f"{y}.pbf"), "wb") as tile:
            tile.write(res.content)

    # write metadata.json
    szoom = f"{zoom}"
    metadata = {
        "bounds": f"{args.min_lon},{args.min_lat},{args.max_lon},{args.max_lat}",
        # metadata.json contains a stringified json inside the json...argh (because it was originally
        # stored in SQLite in an older version of the MVT spec)
        "json": json.dumps({
            "vector_layers": [
                {
                    "id": "osmnodes",
                    "minzoom": szoom,
                    "maxzoom": szoom,
                    "fields": {
                        "mvt_id": "Number"
                    }
                },
                {
                    "id": "speeds",
                    "minzoom": szoom,
                    "maxzoom": szoom,
                    "fields": {
                        "mvt_id": "Number",
                        "speed": "Number",
                        "is_small": "Boolean",
                        "datasource": "String",
                        "weight": "Number",
                        "duration": "Number",
                        "name": "String",
                        "rate": "Number",
                        "is_startpoint": "Boolean"
                    }
                },
                {
                    "id": "turns",
                    "minzoom": szoom,
                    "maxzoom": szoom,
                    "fields": {
                        "mvt_id": "Number",
                        "bearing_in": "Number",
                        "turn_angle": "Number",
                        "cost": "Number",
                        "weight": "Number",
                        "type": "String",
                        "modifier": "String"
                    }
                }
            ]
        })
    }

    with open(os.path.join(tiledir, "metadata.json"), "w") as md:
        json.dump(metadata, md)

    # convert to an OGR format
    LOG.info("Converting MVT to OGR format for output")
    subprocess.run(["ogr2ogr", args.output, f"MVT:{zdir}"])
    
