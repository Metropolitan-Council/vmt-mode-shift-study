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

### Transit network

The `build_transit_network.sh` file builds the transit network from GTFS and the walking street network (used to find transfers). Run it like this, assuming networks are again in `~/vmt-networks`. This will build a file `transit.trjl` with the transit data in it.

    bash build_transit_network.sh --osrm-network ~/vmt-networks/walk/walk.osrm -t 1000 ~/vmt-networks/transit.trjl /path/to/gtfs.zip

_Note:_ If you get an error about not being able to find `libosrmjl.so`, it means either (1) OSRM.jl wasn't installed correctly (see above) or, more likely, (2) `libosrmjl.[so|dylib]` is not in your library path. Look for `libosrmjl.[so|dylib]` and then add the directory it's in to your LD_LIBRARY_PATH. It's most likely in `/usr/local/lib` which is not part of the default search path on WSL.

    export LD_LIBRARY_PATH="/directory/containing/libosrmjl:${LD_LIBRARY_PATH}"

## Doing the routing

### Street routing

To perform street routing, use the `route.jl` script like so, from within this directory (to run from elsewhere, use `--project=/path/to/this/directory`). Replace car with whatever network/mode you're using. If you run into the couldn't find `libosrmjl.so` error, follow the steps above under "Transit network"

    julia -t auto --project route.jl /path/to/tbi_merged.csv ~/vmt-networks/car/car.osrm /path/to/output.gpkg

You can change the output format to any GDAL/OGR supported format with the `--output-driver` option. I used GeoPackage because GeoJSON is unwieldy with this large of a dataset. `-t auto` uses as many threads as your CPU has cores to speed up the routing. On my machine, routing all of the TBI trips by car takes 1 minute 11 seconds, and several minutes to write the output.

Eventually, this will have to be modified for congestion routing, to select an OSRM network based on departure time.

### Transit routing

To perform transit routing, simply add `--transit path/to/transit.trjl` to the `route.jl` command line. It is still necessary to pass an OSRM network as well - this is used to find access and egress to/from transit.

    julia -t auto --project route.jl --transit /path/to/transit.trjl /path/to/tbi_merged.csv ~/vmt-networks/car/car.osrm /path/to/output.gpkg

Transit routing is slower; this takes about 10 minutes on my machine, again with a significant amount of time to write the result to disk.



