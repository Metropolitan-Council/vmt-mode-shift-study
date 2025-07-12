# Routing readme

The scripts `route_street.jl` and `route_transit.jl` perform routing on the TBI data. Getting ready to run them can be a bit tricky, however. First, you need to have OSRM built and installed (see instructions [on the OSRM github](https://github.com/Project-OSRM/osrm-backend#building-from-source)). I  have had no luck installing OSRM on Windows; if you're using Windows, consider using Windows Subsystem for Linux (WSL) for routing. For now, you should install from the `process-segment-flags` branch of `mattwigway/osrm-backend`, but the changes in that branch currently have a pull request to be incorporated back into the main OSRM repository.

Then, you need to install the C++ shim library to allow Julia to communicate with OSRM. To do that, clone the [OSRM.jl](https://github.com/mattwigway/OSRM.jl) Github repository, and within the `cxx/build` directory, run:

    cmake ..
    cmake --build .
    sudo cmake --build . --target install

The difficult part is now over; you just need to install the Julia packages needed for routing. This can be done by running `julia --project` in this directory, and then typing `]instantiate` to install the dependencies.

If you have difficulty with your registry, install Matt's Public Julia Registry

    ]registry add https://github.com/mattwigway/PublicJuliaRegistry.git
    ]add OSM

## Building the network

### Elevation data

For bicycling and walking, routing accounts for elevation differences. In order to do this properly, we need elevation data. We use 1/3 arc-second (~10m) resolution data from the USGS 3D Elevation Program. OSRM will interpolate between the points in the raster, so the resolution is not quite as bad as it sounds.

First, we need to download the data. The script `download_elevation_data.jl` will download all of the GeoTIFF files for the analysis area (each covers one square degree). The script takes one argument, which is the output directory to save the elevation data in. The data requires about 30-35GB of space for all processing to take place.

    download_elevation_data.jl path

From bash, command is 
    cd src/routing
    julia --project download_elevation_data.jl "downloads"

Once the elevation data files are downloaded, several more steps need to happen. They need to be combined into a single file for the analysis area, they need to be reprojected from NAD83 (used by USGS) to WGS84 (used by OSM/OSRM), and they need to be converted to the text-based grid format OSRM requires. OSRM additionally requires that all raster data be integers, so that needs to be done. To minimize rounding errors, we also convert the elevations to millimeters above mean sea level. The shell script `prepare_elevation_data.sh` handles these steps. Since this is a shell script, it will only run on macOS or Linux; if you are using Windows, I recommend installing the Windows Subsystem for Linux. You will need it to run OSRM anyhow. You pass in the path to directory you downloaded the elevation to. 

This will create three new files: combined.tif, which is a GeoTIFF combining all of the elevation tiles into a single dataset; final.asc, which is the OSRM-format raster grid, and final_header.asc, which contains information about the spatial extent of the file. This spatial extent should match the variables declared at the top of `profiles/elevation.lua`.

    bash prepare_elevation_data.sh "downloads"

### Street network

OSRM requires the original `analysis-area.osm.pbf` to be processed into a network, using a "profile" that assigns weights. Eventually, we will have custom profiles that account for slopes, safety, traffic congestion, and so on, but for now we are using the profiles that ship with OSRM. The `build_*_network.sh` scripts will build the networks, taking arguments for the path to the network and the name of the directory where you want the final network to reside (must not already exist; each network should have its own directory). If you're running under WSL, I recommend keeping you networks within WSL (i.e. not under /mnt/c/...) because symbolic links are used during the network build process.

#### Environment variables

The profiles expect three environment variables to be set: `SPEED_DATABASE`, the path to the SQLite speed database (see below), `SPEED_COLUMN`, the column in the database to use for congestion information, and `ELEVATION_FILE`, the path to the `final.asc` file created by the elevation step above.

#### Building the network

I used these commands, putting my networks in `~/vmt-networks/` and using the default installation location for OSRM profiles:

    bash build_<network_name>_network.sh /path/to/analysis-area.osm.pbf ~/vmt-networks/

These will take a few minutes to run.

#### Congestion data

The `car_traffic` profile expects two environment variables to be set, `SPEED_DATABASE` and `SPEED_COLUMN`, referring to the SQLite database and the column to retrieve speeds from. This will be very slow without the proper indices; create them by running `sqlite3 path/to/speed_database.db < prepare_speed_database.sql`

You may need to install the Lua add-on lsqlite3. If you installed sqlite3 using homebrew, install using the code below

    luarocks install lsqlite3 SQLITE_DIR=/usr/local/opt/sqlite3/ SQLITE_LIBDIR=/usr/local/opt/sqlite3/lib/ SQLITE_INCDIR=/usr/local/opt/sqlite3/include/

Note that the car profile is also used in the foot and bicycle profiles to get car speeds for safety perception, so these variables must be set even when not creating congested networks.

OSRM does have functionality to update speeds on the fly, but we do not use this—instead, we just build separate networks for each time period. Running the network build for all of these time periods can be tedious, but we can automate it like this:

    (
        export SPEED_DATABASE="/path/to/streetlight_data.db";
        echo ".schema stl_congestion_data_2019" |
            sqlite3 "$SPEED_DATABASE" |
            grep REAL |
            sed -E 's/^ +"([^"]+).*$/\1/' | 
            xargs -n 1 -Icol env SPEED_COLUMN=col bash _build_street_network.sh ~/vmt-networks/analysis-area.osm.pbf profiles/car_traffic.lua ~/vmt-networks/car_col
    )

(The parentheses are optional, but create a subshell to avoid polluting the main environment in your shell. `export` is necessary because we need SPEED_DATABASE to be available in the variable expansion after `sqlite3` - otherwise that variable expansion occurs before the variable is set).

This will build all of the networks, one for each time period.

### Transit network

The `build_transit_network.sh` file builds the transit network from GTFS and the walking street network (used to find transfers). Run it like this, assuming networks are again in `~/vmt-networks`. This will build a file `transit.trjl` with the transit data in it. 2413.5 specifies a 1.5-mile maximum transfer distance

    bash build_transit_network.sh --osrm-network ~/vmt-networks/walk/walk.osrm -t 2413.5 ~/vmt-networks/transit.trjl /path/to/gtfs.zip

_Note:_ If you get an error about not being able to find `libosrmjl.so`, it means either (1) OSRM.jl wasn't installed correctly (see above) or, more likely, (2) `libosrmjl.[so|dylib]` is not in your library path. Look for `libosrmjl.[so|dylib]` and then add the directory it's in to your LD_LIBRARY_PATH. It's most likely in `/usr/local/lib` which is not part of the default search path on WSL.

    export LD_LIBRARY_PATH="/directory/containing/libosrmjl:${LD_LIBRARY_PATH}"

## Doing the routing

### Street routing

To perform street routing, use the `route.jl` script like so, from within this directory (to run from elsewhere, use `--project=/path/to/this/directory`). Replace car with whatever network/mode you're using. If you run into the couldn't find `libosrmjl.so` error, follow the steps above under "Transit network". The `git rev-parse` portion of the command line inserts the latest commit ID into the output file name so we can track what version of the code produced what output.

    julia -t auto --project route.jl /path/to/tbi_merged.csv ~/vmt-networks/walk/walk.osrm /path/to/output-$(git rev-parse --short 6 HEAD).gpkg

You can change the output format to any GDAL/OGR supported format with the `--output-driver` option. I used GeoPackage because GeoJSON is unwieldy with this large of a dataset. `-t auto` uses as many threads as your CPU has cores to speed up the routing. On my machine, routing all of the TBI trips by car takes 1 minute 11 seconds, and several minutes to write the output. If you're using Windows Subsystem for Linux, you should store the output within WSL, not in `/mnt/c/...` as access to Windows volumes is very slow in WSL. You can move the file to `/mnt/c/` after it's written if you need access to it from Windows.

Add `--bike-lts` to include statistics about bicycle level of traffic stress.

#### Car congestion

Car congestion uses a set of many networks. Since routing is so fast, we just route every trip using congestion data from every time period. You can run this similarly to how the network build was run:

    (
        export SPEED_DATABASE="/path/to/streetlight_data.db";
        echo ".schema stl_congestion_data_2019" | 
        sqlite3 "$SPEED_DATABASE" | 
        grep REAL |
        sed -E 's/^ +"([^"]+).*$/\1/' |
        xargs -n 1 -Icol env julia -t auto --project route.jl /path/to/tbi_merged.csv ~/vmt-networks/car_col/car_col.osrm /path/to/car_col.parquet
    )

### Transit routing

To perform transit routing, simply add `--transit path/to/transit.trjl` to the `route.jl` command line. It is still necessary to pass an OSRM network as well - this is used to find access and egress to/from transit. You can also add `--max-rides` to limit the number of rides that can be taken.

    julia -t auto --project route.jl --transit /path/to/transit.trjl /path/to/tbi_merged.csv ~/vmt-networks/car/car.osrm /path/to/output.gpkg

Transit routing is slower; this takes about 10 minutes on my machine, again with a significant amount of time to write the result to disk.



