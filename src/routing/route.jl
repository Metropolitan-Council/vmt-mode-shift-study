# Perform routing on the street network

using OSRM, DataFrames, CSV, ArchGDAL, ArgParse, Logging, ProgressMeter, Geodesy, ThreadsX, TransitRouter

s = ArgParseSettings()

@add_arg_table! s begin
    "dataset"
        help = "Path to processed TBI dataset"
        required = true
    "network"
        help = "Path to OSRM network"
        required = true
    "output"
        help = "Where to store trip details"
        required = true
    "--transit-network"
        help = "Network for transit routing. If specified, transit routing will be performed and OSRM will only be used for access/egress routing."
    "--output-driver"
        help = "GDAL driver to use to write output, default GPKG"
        default = "GPKG"
    "--osrm-pipeline"
        help = "OSRM pipeline (ch or mld), default mld"
        default = "mld"
end

# Try to check that the path is not inside the git repository. Won't work if you've
# changed the name of the repo on your system, but should help prevent mistakes
within_git_repo(path) = contains(abspath(path), "vmt-mode-shift-study")

# convert Vector{Geodesy.LatLon} to ArchGDAL linestring
function geodesy_to_gdal(latlons)
    geom = ArchGDAL.createlinestring()
    for latlon in latlons
        ArchGDAL.addpoint!(geom, latlon.lon, latlon.lat)
    end
    return geom
end

"Perform street routing using OSRM"
function do_street_route(osrm, data_itr, n_rows)
    ThreadsX.mapi(enumerate(data_itr)) do (i, row)
        if i % 10_000 == 0
            @info "Processed $i trips ($(round(i / n_rows * 100, digits=1))%)"
        end

        routes = route(osrm, LatLon(row.o_lat, row.o_lon), LatLon(row.d_lat, row.d_lon))
        if isempty(routes)
            @warn "Routing failed for trip $(row.trip_id)"
            return (id=row.trip_id, route=nothing)
        else
            return (id=row.trip_id, route=routes[1])
        end
    end
end

"Add the columns stored for street routes to an ArchGDAL layer"
function create_street_columns!(layer)
    ArchGDAL.addfielddefn!(layer, "trip_id", ArchGDAL.OFTString)
    ArchGDAL.addfielddefn!(layer, "duration_seconds", ArchGDAL.OFTReal)
    ArchGDAL.addfielddefn!(layer, "distance_meters", ArchGDAL.OFTReal)
    ArchGDAL.addfielddefn!(layer, "weight", ArchGDAL.OFTReal)
end

"Write a street feature to an ArchGDAL layer"
function write_street_feature!(layer, route)
    ArchGDAL.addfeature(layer) do feature
        ArchGDAL.setgeom!(feature, geodesy_to_gdal(route.route.geometry))
        ArchGDAL.setfield!(feature, 0, route.id)
        ArchGDAL.setfield!(feature, 1, route.route.duration_seconds)
        ArchGDAL.setfield!(feature, 2, route.route.distance_meters)
        ArchGDAL.setfield!(feature, 3, route.route.weight)
    end
end

human_time(seconds, digits=3) = "$(round(Int64, seconds ÷ 3600))h $(round(Int64, seconds ÷ 60))m $(round(seconds % 60, digits=digits))s"

function main(args)
    # check that output data is not being written back into the repository
    within_git_repo(args["output"]) && error("Output must be stored outside the repository!")

    if Threads.nthreads() == 1
        @warn "Running with a single thread. Time is money, use julia -t auto when running for parallelization."
    else
        @info "Routing with $(Threads.nthreads()) threads. Nice."
    end

    transit = !isnothing(args["transit-network"])

    @info "Loading data"
    data = CSV.read(args["dataset"], DataFrame)
    @info "Read $(nrow(data)) trips"

    @info "Loading OSRM"
    osrm = OSRMInstance(args["network"], args["osrm-pipeline"])

    transit_network = if transit
        @info "Loading transit network"
        load_network(args["transit_network"])
    else
        @info "Transit not requested"
        nothing
    end 

    if transit
        time = @elapsed result = do_transit_route(transit_network, osrm, Tables.namedtupleiterator(data), nrow(data))
    else
        time = @elapsed result = do_street_route(osrm, Tables.namedtupleiterator(data), nrow(data))
    end

    not_found_count = sum(map(x -> isnothing(x.route), result))
    @info "Routing complete in $(human_time(time)) seconds. $(not_found_count) trips did not route successfully ($(round(not_found_count / nrow(data) * 100, digits=2))%)"

    outf = args["output"]
    @info "Writing output to $outf"

    # write the result out to disk
    ArchGDAL.create(args["output"], driver=ArchGDAL.getdriver(args["output-driver"])) do ds
        ArchGDAL.createlayer(name="routes", geom=ArchGDAL.wkbLineString, dataset=ds, spatialref=ArchGDAL.importEPSG(4326)) do layer
            if transit
                create_transit_columns!(layer)
            else
                create_street_columns!(layer)
            end

            for (i, route) in enumerate(result)
                if i % 10_000 == 0
                    @info "Wrote $i trips ($(round(i / nrow(data) * 100, digits=1))%)"
                end

                if !isnothing(route.route)
                    if transit
                        write_transit_feature!(layer, route)
                    else
                        write_street_feature!(layer, route)
                    end
                end
            end
        end
    end
end

main(parse_args(s))