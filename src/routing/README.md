# Routing readme

The scripts `route_street.jl` and `route_transit.jl` perform routing on the TBI data. Getting ready to run them can be a bit tricky, however. First, you need to have OSRM built and installed (see instructions [on the OSRM github](https://github.com/Project-OSRM/osrm-backend#building-from-source)). I  have had no luck installing OSRM on Windows; if you're using Windows, consider using Windows Subsystem for Linux (WSL) for routing.

Then, you need to install the C++ shim library to allow Julia to communicate with OSRM. To do that, clone the [OSRM.jl](https://github.com/mattwigway/OSRM.jl) Github repository, and within the `cxx/build` directory, run:

    cmake ..
    cmake --build .
    sudo cmake --build . --target install

The difficult part is now over; you just need to install the Julia packages needed for routing. This can be done by running `julia --project` in this directory, and then typing `]instantiate` to install the dependencies.

## Building the network

### Street network

OSRM requires the original `analysis-area.osm.pbf` to be processed into a network, using a "profile" that assigns weights. Eventually, we will have custom profiles that account for slopes, safety, traffic congestion, and so on, but for now we are using the profiles that ship with OSRM. The `build_network.sh` script will build the network, taking arguments for the path to the network, the path to the profile, and the name of the directory where you want the final network to reside (must not already exist). If you're running under WSL, I recommend keeping you networks within WSL (i.e. not under /mnt/c/...) because symbolic links are used during the network build process. I used these commands, putting my networks in `~/vmt-networks/<network_name>` and using the default installation location for OSRM profiles:

    bash build_street_network.sh /path/to/analysis-area.osm.pbf /usr/local/share/osrm/profiles/car.lua ~/vmt-networks/car
    bash build_street_network.sh /path/to/analysis-area.osm.pbf /usr/local/share/osrm/profiles/foot.lua ~/vmt-networks/walk
    bash build_street_network.sh /path/to/analysis-area.osm.pbf /usr/local/share/osrm/profiles/bicycle.lua ~/vmt-networks/bike

These each took about a minute on my desktop, but _much_ longer on my laptop---likely due to memory requirements. I have 128GB on my desktop.

#### Congestion data

The `car_traffic` profile expects two environment variables to be set, `SPEED_DATABASE` and `SPEED_COLUMN`, referring to the SQLite database and the column to retrieve speeds from. This will be very slow without the proper indices; create them by running `sqlite3 path/to/speed_database.db < prepare_speed_database.sql`

Note that the car profile is also used in the foot and bicycle profiles to get car speeds for safety perception, so these variables must be set even when not creating congested networks.

OSRM does have functionality to update speeds on the fly, but we do not use this—instead, we just build separate networks for each time period. Running the network build for all of these time periods can be tedious, but we can automate it like this:

    (
        export SPEED_DATABASE="/path/to/streetlight_data.db";
        echo ".schema stl_congestion_data_2019" |
            sqlite3 "$SPEED_DATABASE" |
            grep REAL |
            sed -E 's/^ +"([^"]+).*$/\1/' | 
            xargs -n 1 -Icol env SPEED_COLUMN=col bash build_street_network.sh /path/to/analysis-area.osm.pbf /usr/local/share/osrm/profiles/car.lua ~/vmt-networks/car_col
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
        xargs -n 1 -Icol env julia -t auto --project route.jl /path/to/tbi_merged.csv ~/vmt-networks/car_col/car_col.osrm /path/to/car_col.gpkg
    )

### Transit routing

To perform transit routing, simply add `--transit path/to/transit.trjl` to the `route.jl` command line. It is still necessary to pass an OSRM network as well - this is used to find access and egress to/from transit. You can also add `--max-rides` to limit the number of rides that can be taken.

    julia -t auto --project route.jl --transit /path/to/transit.trjl /path/to/tbi_merged.csv ~/vmt-networks/car/car.osrm /path/to/output.gpkg

Transit routing is slower; this takes about 10 minutes on my machine, again with a significant amount of time to write the result to disk.



