# This contains automated tests for the baseline car network, to ensure that speeds are applied correctly
# It compares expected vs actual speeds for all edges that have streetlight entries.
# OSRM rounds segment-level times to deciseconds (0.1 second), which can cause significant speed
# deviations on short and fast links. This script identifies edges that deviate from the StreetLight predicted
# travel time by more than 0.05 * (number of nodes - 1) + 0.01 * (length in meters); the first term is how much the
# quantization of each node-to-node segment could change travel times, and the second term accounts for rounding errors
# in unit conversion and distance calculation.

import OSRM.Toolchain: OSRMToolchain, get_node_ids, get_geometry 
import OSRM: OSRMInstance, route
import GeoFormatTypes as GFT
using Test, Geodesy, SQLite, DBInterface, StatsBase, Plots, ArgParse, LibSpatialIndex, GeoDataFrames,
    ArchGDAL, DataFrames, CSV

const UTM = GFT.EPSG(26915)
const WGS84 = GFT.EPSG(4326)

include("util.jl")

function get_speed(stmt, fr, to)::Tuple{Union{Nothing, Float64}, Int64}
    res = DBInterface.execute(stmt, (fr, to))
    if isempty(res)
        return nothing, -1
    else
        row = first(res)
        return (row.speed::Float64, row.way_id::Int64)
    end
end

get_nacto_speed(stmt, way)::Float64 = convert(Float64, first(DBInterface.execute(stmt, (way,))).speed_cap_mph)

function main(raw_args)
    s = ArgParseSettings()
    @add_arg_table! s begin
        "network"
            help = "OSRM network file"
        "streetlight_db"
            help = "StreetLight database"
        "column"
            help = "Which speed column (period) to use from the StreetLight database"
        "--nacto-cap"
            help = "Apply NACTO caps (pass in path to database containing speed caps)"
            metavar = "SPEED_CAP_DB"
    end

    args = parse_args(raw_args, s)

    toolchain = OSRMToolchain(args["network"])

    conn = SQLite.DB(args["streetlight_db"])
    stmt = SQLite.Stmt(conn, """
        SELECT DISTINCT "$(args["column"])" AS speed, n1.way_id AS way_id
            FROM stl_congestion_data_2019 c
            LEFT JOIN stl_nodes_table n1 ON (c.seg_id = n1.seg_id)
            LEFT JOIN stl_nodes_table n2 ON (c.seg_id = n2.seg_id AND n1.way_id = n2.way_id AND ABS(n1.seg_seqid - n2.seg_seqid) = 1)

        WHERE n1.node_id = ?
        AND n2.node_id = ?
        AND direction = CASE n2.seg_seqid - n1.seg_seqid
            WHEN 1 THEN 'forward'
            WHEN -1 THEN 'reverse'
        END
    """)

    nacto_db = nothing
    nacto_stmt = nothing
    if !isnothing(args["nacto-cap"])
        nacto_db = SQLite.DB(args["nacto-cap"])
        nacto_stmt = SQLite.Stmt(nacto_db, "SELECT speed_cap_mph FROM way_speeds WHERE way_id = ?")
    else
        nothing
    end

 
    correct = 0
    incorrect = 0
    missng = 0

    speed_differences = Float64[]

    for (eidx, edge) in pairs(toolchain.edge_based_nodes)
        if eidx % 10000 == 0
            @info "Processed $eidx edges"
        end

        this_edge_incomplete = false
        sum_w_speeds = zero(Float64)
        sum_dists = zero(Float64)
        geom = get_geometry(toolchain, edge)::Vector{LatLon{Float64}}
        nodes = get_node_ids(toolchain, edge)::Vector{Int64}
        prev_way_id = -1
        way_id = -1
        nacto_speed = zero(Float64)
        for (n1, p1, n2, p2) in zip(nodes[begin:end-1], geom[begin:end-1], nodes[begin+1:end], geom[begin+1:end])
            speed, way_id = get_speed(stmt, n1, n2)

            if isnothing(speed)
                this_edge_incomplete = true
                break
            else
                # nacto speeds may also vary within an edge if two ways were put together because the did not intersect
                # with anything else; OSRM will use the average speed. Additionally, caps are applied to each segment, not the
                # entire way, so it is possible to have a situation where part of an edge is capped and part is not because
                # the cap is non-binding in part of the way
                if !isnothing(args["nacto-cap"])
                    if way_id != prev_way_id
                        nacto_speed = get_nacto_speed(nacto_stmt, way_id)
                        prev_way_id = way_id
                    end

                    speed = min(speed, nacto_speed * 0.8)
                end

                dist = euclidean_distance(p1, p2)::Float64
                sum_w_speeds += speed * dist
                sum_dists += dist
            end
        end

        if !this_edge_incomplete
            expected_speed = sum_w_speeds / sum_dists * 1.609
            actual_speed = getspeedkmh(toolchain, eidx)
            push!(speed_differences, expected_speed - actual_speed)
            
            # OSRM quantizes time to deciseconds (0.1 seconds). On short links at high speeds this can significantly affect speeds,
            # so we compare times instead, and call it good if the time is within 1 second of expected.
            expected_time = sum_dists / expected_speed * 3.6
            actual_time = toolchain.edge_based_node_durations[eidx] / 10
            # Each node-to-node segment gets rounded to deciseconds, so each one can accumulate an error of
            # 0.05 seconds. We add an additional 1/100 of a second for each meter to account for differences in distance
            # calculation, rounding errors in unit conversion, etc.
            if isapprox(actual_time, expected_time; atol=0.05 * (length(nodes) - 1) + 0.01 * sum_dists) || sum_dists < 2
                correct += 1
            else
                incorrect += 1
                @warn "Speeds do not match: expected $(round(expected_speed, digits=2)) kmh, found $(round(actual_speed, digits=2)) kmh, at edge containing nodes $nodes (distance $(round(sum_dists, digits=1))m)"
            end
        else
            missng += 1
        end
    end

    @info "$correct edges had expected speed information"
    @info "$incorrect edges had unexpected speed information"
    @info "$missng edges had missing speed information"


    histogram(speed_differences, bins=60)
    Plots.xlabel!("Expected (StreetLight) - actual (OSRM) (kmh)")
    Plots.savefig(isnothing(args["nacto-cap"]) ? "speed_baseline_comparison.png" : "speed_scenario_comparison.png")

    println("Minimum: $(round(minimum(speed_differences), sigdigits=3))")
    println("Maximum: $(round(maximum(speed_differences), sigdigits=3))")
    for pctile in [0.05, 0.5, 1, 2.5, 5, 25, 50, 75, 95, 97.5, 99, 99.5, 99.95]
        println("Percentile $pctile: $(round(percentile(speed_differences, pctile), sigdigits=3))")
    end
end

main(ARGS)