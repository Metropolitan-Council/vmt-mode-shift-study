# Perform routing on the street network

using OSRM, DataFrames, CSV, ArchGDAL, ArgParse, Logging, ProgressMeter, Geodesy, ThreadsX,
    TransitRouter, Dates

# used for transit routing, all transit routes will use the first
# day after this date that is the same day of the week as the original
# trip.
const REPRESENTATIVE_WEEK = Date(2023, 1, 23)

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
    "--limit"
        help = "Maximum number of routes to route (useful in testing)"
        arg_type = Int
        default = -1
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

#### STREET ROUTING

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

#### TRANSIT ROUTING

"select a representative date/time - correct day of week but within the GTFS service window"
#TODO automated test
select_representative_date(date) = Dates.tonext(x -> dayofweek(x) == dayofweek(date), REPRESENTATIVE_WEEK)

function do_transit_route(net, osrm, data_itr, n_rows)
    ThreadsX.mapi(enumerate(data_itr)) do (i, row)
        if i % 10_000 == 0
            @info "Processed $i trips ($(round(i / n_rows * 100, digits=1))%)"
        end

        date = select_representative_date(row.travel_date)

        result = street_raptor(
            net,
            osrm,
            osrm, # same access and egress router
            LatLon(row.o_lat, row.o_lon),
            [LatLon(row.d_lat, row.d_lon)], # single destination
            DateTime(
                date,
                row.depart_time  # TODO reverse routing
            )
        )

        path = trace_path(net, result, 1)
        return (id=row.trip_id, route=ismissing(path) ? nothing : path, date=date)
    end
end

function create_transit_columns!(layer)
    ArchGDAL.addfielddefn!(layer, "trip_id", ArchGDAL.OFTString)
    ArchGDAL.addfielddefn!(layer, "leg_index", ArchGDAL.OFTInteger)
    ArchGDAL.addfielddefn!(layer, "start_time", ArchGDAL.OFTDateTime)
    ArchGDAL.addfielddefn!(layer, "end_time", ArchGDAL.OFTDateTime)
    ArchGDAL.addfielddefn!(layer, "origin_stop_id", ArchGDAL.OFTString)
    ArchGDAL.addfielddefn!(layer, "origin_stop_name", ArchGDAL.OFTString)
    ArchGDAL.addfielddefn!(layer, "destination_stop_id", ArchGDAL.OFTString)
    ArchGDAL.addfielddefn!(layer, "destination_stop_name", ArchGDAL.OFTString)
    ArchGDAL.addfielddefn!(layer, "route_id", ArchGDAL.OFTString)
    ArchGDAL.addfielddefn!(layer, "route_short_name", ArchGDAL.OFTString)
    ArchGDAL.addfielddefn!(layer, "route_long_name", ArchGDAL.OFTString)
    ArchGDAL.addfielddefn!(layer, "route_type", ArchGDAL.OFTInteger)
    ArchGDAL.addfielddefn!(layer, "leg_type", ArchGDAL.OFTString)
end

function setfield_with_missing!(feature, field, value)
    if ismissing(value) || isnothing(value)
        ArchGDAL.setfieldnull!(feature, field)
    else
        ArchGDAL.setfield!(feature, field, value)
    end
end

function write_transit_feature!(layer, route)
    for (legidx, leg) in enumerate(route.route)
        ArchGDAL.addfeature(layer) do feature
            ArchGDAL.setgeom!(feature, geodesy_to_gdal(leg.geometry))
            setfield_with_missing!(feature, 0, route.id)
            setfield_with_missing!(feature, 1, legidx)
            setfield_with_missing!(feature, 2, leg.start_time)
            setfield_with_missing!(feature, 3, leg.end_time)
            
            if leg.type != TransitRouter.access
                setfield_with_missing!(feature, 4, leg.origin_stop.stop_id)
                setfield_with_missing!(feature, 5, leg.origin_stop.stop_name)
            else
                ArchGDAL.setfieldnull!.(Ref(feature), 4:5)
            end
            
            if leg.type != TransitRouter.egress
                setfield_with_missing!(feature, 6, leg.destination_stop.stop_id)
                setfield_with_missing!(feature, 7, leg.destination_stop.stop_name)
            else
                ArchGDAL.setfieldnull!.(Ref(feature), 6:7)
            end
            
            if leg.type == TransitRouter.transit
                setfield_with_missing!(feature, 8, leg.route.route_id)
                setfield_with_missing!(feature, 9, leg.route.route_short_name)
                setfield_with_missing!(feature, 10, leg.route.route_long_name)
                setfield_with_missing!(feature, 11, leg.route.route_type)
            else
                ArchGDAL.setfieldnull!.(Ref(feature), 8:11)
            end

            ArchGDAL.setfield!(feature, 12, repr(leg.type))
        end
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

    @info "Loading data"
    data = CSV.read(args["dataset"], DataFrame)
    @info "Read $(nrow(data)) trips"

    if args["limit"] != -1
        data = data[1:min(nrow(data), args["limit"]), :]
        @info "Data truncated to first $(nrow(data)) rows"
    end

    @info "Loading OSRM"
    osrm = OSRMInstance(args["network"], args["osrm-pipeline"])

    transit = !isnothing(args["transit-network"])

    transit_network = if transit
        @info "Loading transit network"
        load_network(args["transit-network"])
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

#=
Round 3, stop 5804, transfer from stop 7355, no transfer in network
Round 3, stop 5805, transfer from stop 7355, no transfer in network
Round 3, stop 5806, transfer from stop 1979, no transfer in network
Round 3, stop 5808, transfer from stop 5902, no transfer in network
Round 3, stop 5809, transfer from stop 5902, no transfer in network
Round 3, stop 5810, transfer from stop 304, no transfer in network
Round 3, stop 5812, transfer from stop 5813, no transfer in network
Round 3, stop 5815, transfer from stop 5994, no transfer in network
Round 3, stop 5821, transfer from stop 3187, no transfer in network
Round 3, stop 5822, transfer from stop 3187, no transfer in network
Round 3, stop 5823, transfer from stop 3187, no transfer in network
Round 3, stop 5824, transfer from stop 3187, no transfer in network
Round 3, stop 5825, transfer from stop 5827, no transfer in network
Round 3, stop 5826, transfer from stop 5827, no transfer in network
Round 3, stop 5828, transfer from stop 5827, no transfer in network
Round 3, stop 5829, transfer from stop 7273, no transfer in network
Round 3, stop 5832, transfer from stop 7117, no transfer in network
Round 3, stop 5833, transfer from stop 856, no transfer in network
Round 3, stop 5834, transfer from stop 6234, no transfer in network
Round 3, stop 5835, transfer from stop 841, no transfer in network
Round 3, stop 5836, transfer from stop 841, no transfer in network
Round 3, stop 5837, transfer from stop 856, no transfer in network
Round 3, stop 5838, transfer from stop 847, no transfer in network
Round 3, stop 5839, transfer from stop 856, no transfer in network
Round 3, stop 5840, transfer from stop 856, no transfer in network
Round 3, stop 5841, transfer from stop 856, no transfer in network
Round 3, stop 5842, transfer from stop 856, no transfer in network
Round 3, stop 5843, transfer from stop 856, no transfer in network
Round 3, stop 5844, transfer from stop 5845, no transfer in network
Round 3, stop 5846, transfer from stop 6738, no transfer in network
Round 3, stop 5847, transfer from stop 841, no transfer in network
Round 3, stop 5848, transfer from stop 841, no transfer in network
Round 3, stop 5849, transfer from stop 4350, no transfer in network
Round 3, stop 5850, transfer from stop 7951, no transfer in network
Round 3, stop 5851, transfer from stop 5863, no transfer in network
Round 3, stop 5852, transfer from stop 5861, no transfer in network
Round 3, stop 5853, transfer from stop 5860, no transfer in network
Round 3, stop 5865, transfer from stop 5876, no transfer in network
Round 3, stop 5866, transfer from stop 5876, no transfer in network
Round 3, stop 5867, transfer from stop 5876, no transfer in network
Round 3, stop 5868, transfer from stop 5875, no transfer in network
Round 3, stop 5869, transfer from stop 1218, no transfer in network
Round 3, stop 5870, transfer from stop 5874, no transfer in network
=#