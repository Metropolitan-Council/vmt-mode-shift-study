# Perform routing on the street network

using OSRM, DataFrames, CSV, ArchGDAL, ArgParse, Logging, ProgressMeter, Geodesy, ThreadsX,
    TransitRouter, Dates, Serialization

# Maximum distance for access, egress, or transfers from transit
const MAX_LEG_WALK_DIST_METERS = 1.5 * 1609 # 1.5 mile walk allowed

# How much earlier than the observed departure we allow departure-constrained trips to depart
const DEPARTURE_CONSTRAINED_FLEXIBILITY_SECONDS = 300 # five minutes

# How much later than the observed arrival we allow arrival-constrained trips to arrive
const ARRIVAL_CONSTRAINED_FLEXIBILITY_SECONDS = 300 # five minutes

# Some trips may be flexible at the departure end, and some at the arrival end. Whichever purpose category
# is earlier in this list will be the end that is constrained. Anything not in the list is assumed
# to be after the end of the list
const CONSTRAINED_PURPOSE_CATEGORY_PECKING_ORDER = [
    "Work"
]

# Like most transit routing algorithms, RAPTOR and range-RAPTOR guarantee they will find the earliest arrival at the destination,
# not necessarily the shortest path. However, range-RAPTOR and clever filtering allow us to find the shortest path,
# but only if it departs within the range-RAPTOR period. This controls the length of the range-RAPTOR period after the requested
# departure time. Reverse routing does not suffer from this issue, as the burn in period extends until the desired arrival time,
# so the shortest path is guaranteed to be found.
# We allow compressing up to 1 hour of extra wait time off the start of the trip.
const RANGE_RAPTOR_BURN_IN_PERIOD_SECONDS = 3600

# When routing in reverse, how far back in time to go to find a trip?
const RANGE_RAPTOR_MAX_REVERSE_TIME = 24 * 3600

# how much to move a point to make geometries valid when the geometry
# is two identical points. Generally caused by transfers between stops coded as coincident
# in the GTFS.
const GEOMETRY_VALIDITY_EPSILON_DEGREES = 1e-7 # 1e-7 degrees ≈ 1 cm

# used for transit routing, all transit routes will use the first
# day after this date that is the same day of the week as the original
# trip.
const REPRESENTATIVE_WEEK = Date(2019, 10, 19)

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
    "--trip"
        help = "Only route this trip ID"
        nargs = '+'
        action = :store_arg
    "--bike-lts"
        help = "Consider bicycle LTS in output"
        action = :store_true
    "--max-rides"
        help = "Maximum number of rides for transit"
        arg_type = Int
        default = 4
end

# Try to check that the path is not inside the git repository. Won't work if you've
# changed the name of the repo on your system, but should help prevent mistakes
within_git_repo(path) = contains(abspath(path), "vmt-mode-shift-study")

# convert Vector{Geodesy.LatLon} to ArchGDAL linestring
function geodesy_to_gdal(latlons)
    # first, check that the geometry is valid (i.e. does not contain only one point, or two identical points)
    if length(latlons) == 1
        latlons = [latlons[1], latlons[1]]
        # will be jittered below
    end

    # This can happen when there is a transfer leg between two coincident stops
    # There will be no transfer leg generated when boarding a trip at the same stop you previously
    # alighted from, but sometimes GTFS contains multiple stops with identical coordinates.
    if length(latlons) == 2 && first(latlons) ≈ last(latlons)
        latlons = [latlons[1], LatLon(latlons[2].lat + GEOMETRY_VALIDITY_EPSILON_DEGREES, latlons[2].lon + GEOMETRY_VALIDITY_EPSILON_DEGREES)]
    end

    geom = ArchGDAL.createlinestring()
    for latlon in latlons
        ArchGDAL.addpoint!(geom, latlon.lon, latlon.lat)
    end
    return geom
end

#### STREET ROUTING

"Perform street routing using OSRM"
function do_street_route(osrm, data_itr, n_rows, bikelts)
    # uncomment for single thread debugging
    #map(enumerate(data_itr)) do (i, row)
    ThreadsX.mapi(enumerate(data_itr)) do (i, row)
        if i % 10_000 == 0
            @info "Processed $i trips ($(round(i / n_rows * 100, digits=1))%)"
        end

        routes = route(osrm, LatLon(row.o_lat, row.o_lon), LatLon(row.d_lat, row.d_lon))
        if isempty(routes)
            @warn "Routing failed for trip $(row.trip_id)"
            return (id=row.trip_id, route=nothing)
        else
            if bikelts
                segments = split_route_by_lts(routes[1])
                return (id=row.trip_id, route=routes[1], segments=segments)
            else
                return (id=row.trip_id, route=routes[1])
            end
        end
    end
end

struct RouteSegment
    lts::Int32
    geometry::Vector{LatLon}
    distance_meters::Float64
end


function split_route_by_lts(route::OSRM.Route)
    result = RouteSegment[]

    # annoyingly, we don't have a clean way to split up the route by LTS
    # instead, we go through the steps and find coordinates where LTS changes, and
    # then match those up with the overall route geometry
    current_coord_index = 1

    @assert length(route.legs) == 1

    current_lts = -1

    for (stepidx, step) in enumerate(route.legs[1].steps)
        for (intidx, intersection) in enumerate(step.intersections)
            if isnothing(intersection.classes) && stepidx == length(route.legs[1].steps) && intidx == length(step.intersections)
                # classes are missing on last "intersection" arriving at destination
                continue
            end

            lts = if "lts1" ∈ intersection.classes
                1
            elseif "lts2" ∈ intersection.classes
                2
            elseif "lts3" ∈ intersection.classes
                3
            elseif "lts4" ∈ intersection.classes
                4
            else
                error("No LTS found")
            end

            if lts != current_lts
                if current_lts == -1
                    # first segment
                    current_lts = lts
                else
                    # write out the current segment
                    # figure out where we are in the geometry
                    new_coord_idx = current_coord_index + findfirst(route.geometry[current_coord_index:end] .≈ Ref(intersection.location)) - 1
                    @assert !isnothing(new_coord_idx)

                    geom = route.geometry[current_coord_index:new_coord_idx]
                    # -1 because these are the distances _between_ coordinates
                    distance_meters = sum(route.legs[1].annotation.distance_meters[current_coord_index:(new_coord_idx - 1)])

                    # duration and weight are non-trivial, because the annotation does not include
                    # turn costs. So just summing up duration the way we do distance won't work. For now,
                    # punt on this, and just don't include duration/weight at the segment level.

                    push!(result, RouteSegment(current_lts, geom, distance_meters))

                    current_lts = lts
                    current_coord_index = new_coord_idx
                end
            end
        end
    end

    # finish up
    geom = route.geometry[current_coord_index:end]
    # -1 because these are the distances _between_ coordinates
    distance_meters = sum(route.legs[1].annotation.distance_meters[current_coord_index:end])


    push!(result, RouteSegment(current_lts, geom, distance_meters))
end

"Add the columns stored for street routes to an ArchGDAL layer"
function create_street_columns!(layer, bikelts)
    ArchGDAL.addfielddefn!(layer, "trip_id", ArchGDAL.OFTString)
    ArchGDAL.addfielddefn!(layer, "duration_seconds", ArchGDAL.OFTReal)
    ArchGDAL.addfielddefn!(layer, "distance_meters", ArchGDAL.OFTReal)
    ArchGDAL.addfielddefn!(layer, "weight", ArchGDAL.OFTReal)

    if bikelts
        for lts in 1:4
            ArchGDAL.addfielddefn!(layer, "distance_meters_$lts", ArchGDAL.OFTReal)
        end
    end
end

sum_if_nonzero(v) = isempty(v) ? zero(Float64) : sum(v)

"Write a street feature to an ArchGDAL layer"
function write_street_feature!(layer, route)
    ArchGDAL.addfeature(layer) do feature
        ArchGDAL.setgeom!(feature, geodesy_to_gdal(route.route.geometry))
        ArchGDAL.setfield!(feature, 0, route.id)
        ArchGDAL.setfield!(feature, 1, route.route.duration_seconds)
        ArchGDAL.setfield!(feature, 2, route.route.distance_meters)
        ArchGDAL.setfield!(feature, 3, route.route.weight)

        if :segments ∈ keys(route)
            for lts in 1:4
                lts_segments = filter(s -> s.lts == lts, route.segments)
                ArchGDAL.setfield!(feature, 3 + lts, sum_if_nonzero(map(s -> s.distance_meters, lts_segments)))
            end
        end
    end
end

# create the layer for the bike segments data
function create_bike_segment_columns!(layer)
    ArchGDAL.addfielddefn!(layer, "trip_id", ArchGDAL.OFTString)
    ArchGDAL.addfielddefn!(layer, "segment_index", ArchGDAL.OFTReal)
    ArchGDAL.addfielddefn!(layer, "lts", ArchGDAL.OFTInteger)
    ArchGDAL.addfielddefn!(layer, "distance_meters", ArchGDAL.OFTReal)
end

function write_bike_segments!(layer, route)
    for (i, segment) in enumerate(route.segments)
        ArchGDAL.addfeature(layer) do feature
            ArchGDAL.setgeom!(feature, geodesy_to_gdal(segment.geometry))
            ArchGDAL.setfield!(feature, 0, route.id)
            ArchGDAL.setfield!(feature, 1, i)
            ArchGDAL.setfield!(feature, 2, segment.lts)
            ArchGDAL.setfield!(feature, 3, segment.distance_meters)
        end
    end
end

#### TRANSIT ROUTING

"select a representative date/time - correct day of week but within the GTFS service window"
#TODO automated test
select_representative_date(date) = Dates.tonext(x -> dayofweek(x) == dayofweek(date), REPRESENTATIVE_WEEK)

function do_transit_route(net, osrm, max_rides, data_itr, n_rows)
    # uncomment for single-thread debugging
    #map(enumerate(data_itr)) do (i, row)
    ThreadsX.mapi(enumerate(data_itr)) do (i, row)
        if i % 10_000 == 0
            @info "Processed $i trips ($(round(i / n_rows * 100, digits=1))%)"
        end

        date = select_representative_date(row.travel_date)

        # figure out if we're routing forwards or backwards (which end of trip is constrained)
        # if purpose is not in constrained categories, it is lowest priority (typemax(Int64))
        origin_priority = something(findfirst(row.o_purpose_category .== CONSTRAINED_PURPOSE_CATEGORY_PECKING_ORDER), typemax(Int64))
        destination_priority = something(findfirst(row.d_purpose_category .== CONSTRAINED_PURPOSE_CATEGORY_PECKING_ORDER), typemax(Int64))

        # we route in reverse iff the destination is higher priority (smaller number) than the origin priority
        # otherwise (if they are equal or origin priority is higher) we route forwards
        reverse_route = destination_priority < origin_priority

        paths = if reverse_route
            all_paths = street_raptor(
                net,
                osrm,
                osrm, # same access and egress router
                LatLon(row.o_lat, row.o_lon),
                [LatLon(row.d_lat, row.d_lon)], # single destination
                DateTime(
                    date,
                    row.arrive_time
                ),
                -RANGE_RAPTOR_MAX_REVERSE_TIME, # search up to this amount of time before the requested arrival
                max_access_distance_meters=MAX_LEG_WALK_DIST_METERS,
                max_egress_distance_meters=MAX_LEG_WALK_DIST_METERS,
                max_rides=max_rides
            )[1]  # just one destination

            # sort by arrival time, get all paths that arrive within the grace period
            if !isempty(all_paths)
                filter(p -> p[end].end_time ≤ DateTime(date, row.arrive_time) + Second(ARRIVAL_CONSTRAINED_FLEXIBILITY_SECONDS), all_paths)
            else
                Vector{TransitRouter.Leg}[]
            end
        else
            all_paths = street_raptor(
                net,
                osrm,
                osrm, # same access and egress router
                LatLon(row.o_lat, row.o_lon),
                [LatLon(row.d_lat, row.d_lon)], # single destination
                DateTime(
                    date,
                    row.depart_time - Second(DEPARTURE_CONSTRAINED_FLEXIBILITY_SECONDS)
                ),
                # run range-RAPTOR until departure time + burn in period
                RANGE_RAPTOR_BURN_IN_PERIOD_SECONDS + DEPARTURE_CONSTRAINED_FLEXIBILITY_SECONDS,
                max_access_distance_meters=MAX_LEG_WALK_DIST_METERS,
                max_egress_distance_meters=MAX_LEG_WALK_DIST_METERS,
                max_rides=max_rides
            )[1]

            # get all paths that depart within the grace period, plus one more
            if !isempty(all_paths)
                sort!(all_paths, by=p -> p[begin].start_time)
                lim = findfirst(p -> p[begin].start_time ≥ DateTime(date, row.depart_time), all_paths)
                if isnothing(lim)
                    all_paths
                else
                    all_paths[begin:lim]
                end
            else
                Vector{TransitRouter.Leg}[]
            end
        end

        if length(paths) > 10
            @warn "Trip $(row.trip_id) has $(length(paths)) paths"
        end

        return (id=row.trip_id, route=paths, date=date, reverse=reverse_route)
    end
end

function create_transit_columns!(layer)
    ArchGDAL.addfielddefn!(layer, "trip_id", ArchGDAL.OFTString)
    ArchGDAL.addfielddefn!(layer, "option_index", ArchGDAL.OFTInteger)
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
    ArchGDAL.addfielddefn!(layer, "distance_meters", ArchGDAL.OFTReal)
    ArchGDAL.addfielddefn!(layer, "reverse", ArchGDAL.OFTInteger)
end

function setfield_with_missing!(feature, field, value)
    if ismissing(value) || isnothing(value)
        ArchGDAL.setfieldnull!(feature, field)
    else
        ArchGDAL.setfield!(feature, field, value)
    end
end

function write_transit_feature!(layer, route)
    for (optidx, opt) in enumerate(route.route)
        for (legidx, leg) in enumerate(opt)
            ArchGDAL.addfeature(layer) do feature
                ArchGDAL.setgeom!(feature, geodesy_to_gdal(leg.geometry))
                setfield_with_missing!(feature, 0, route.id)
                setfield_with_missing!(feature, 1, optidx)
                setfield_with_missing!(feature, 2, legidx)
                setfield_with_missing!(feature, 3, leg.start_time)
                setfield_with_missing!(feature, 4, leg.end_time)
                
                if leg.type != TransitRouter.access
                    setfield_with_missing!(feature, 5, leg.origin_stop.stop_id)
                    setfield_with_missing!(feature, 6, leg.origin_stop.stop_name)
                else
                    ArchGDAL.setfieldnull!.(Ref(feature), 5:6)
                end
                
                if leg.type != TransitRouter.egress
                    setfield_with_missing!(feature, 7, leg.destination_stop.stop_id)
                    setfield_with_missing!(feature, 8, leg.destination_stop.stop_name)
                else
                    ArchGDAL.setfieldnull!.(Ref(feature), 7:8)
                end
                
                if leg.type == TransitRouter.transit
                    setfield_with_missing!(feature, 9, leg.route.route_id)
                    setfield_with_missing!(feature, 10, leg.route.route_short_name)
                    setfield_with_missing!(feature, 11, leg.route.route_long_name)
                    setfield_with_missing!(feature, 12, leg.route.route_type)
                else
                    ArchGDAL.setfieldnull!.(Ref(feature), 9:12)
                end

                ArchGDAL.setfield!(feature, 13, repr(leg.type))
                setfield_with_missing!(feature, 14, leg.distance_meters)
                ArchGDAL.setfield!(feature, 15, route.reverse ? 1 : 0)
            end
        end
    end
end

human_time(seconds, digits=3) = "$(round(Int64, seconds ÷ 3600))h $(round(Int64, seconds ÷ 60))m $(round(seconds % 60, digits=digits))s"

function main(args)
    # check that output data is not being written back into the repository
    within_git_repo(args["output"]) && error("Output must be stored outside the repository, not in $(args["output"])")

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

    if !isempty(args["trip"])
        data = data[data.trip_id .∈ Ref(args["trip"]), :]
        @info "Retained $(nrow(data)) rows"
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
        time = @elapsed result = do_transit_route(transit_network, osrm, args["max-rides"], Tables.namedtupleiterator(data), nrow(data))
    else
        time = @elapsed result = do_street_route(osrm, Tables.namedtupleiterator(data), nrow(data), args["bike-lts"])
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
                create_street_columns!(layer, args["bike-lts"])
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

        if args["bike-lts"]
            ArchGDAL.createlayer(name="segments",  geom=ArchGDAL.wkbLineString, dataset=ds, spatialref=ArchGDAL.importEPSG(4326)) do layer
                create_bike_segment_columns!(layer)
                for (i, route) in enumerate(result)
                    if i % 10_000 == 0
                        @info "Wrote segments for $i trips ($(round(i / nrow(data) * 100, digits=1))%)"
                    end

                    write_bike_segments!(layer, route)
                end
            end
        end
    end
end

main(parse_args(s))