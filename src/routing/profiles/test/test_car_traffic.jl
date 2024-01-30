# This contains automated tests for the baseline car network, to ensure that speeds are applied correctly

import OSRM.Toolchain: OSRMToolchain, get_node_ids, get_geometry 
import OSRM: OSRMInstance, route
using Test, Geodesy, SQLite, DBInterface, StatsBase, UnicodePlots

include("util.jl")

function get_speed(stmt, fr, to)::Union{Nothing, Float64}
    res = DBInterface.execute(stmt, (fr, to))
    if isempty(res)
        return nothing
    else
        return first(res).speed::Float64
    end
end

function main(network, streetlight_db, column)
    toolchain = OSRMToolchain(network)

    conn = SQLite.DB(streetlight_db)
    stmt = SQLite.Stmt(conn, """
        SELECT DISTINCT "$column" AS speed
            FROM stl_congestion_data_2019 c
            LEFT JOIN stl_nodes_table n1 ON (c.seg_id = n1.seg_id)
            LEFT JOIN stl_nodes_table n2 ON (c.seg_id = n2.seg_id AND ABS(n1.seg_seqid - n2.seg_seqid) = 1)

        WHERE n1.node_id = ?
        AND n2.node_id = ?
        AND direction = CASE n2.seg_seqid - n1.seg_seqid
            WHEN 1 THEN 'forward'
            WHEN -1 THEN 'reverse'
        END
    """)
 
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
        for (n1, p1, n2, p2) in zip(nodes[begin:end-1], geom[begin:end-1], nodes[begin+1:end], geom[begin+1:end])
            speed = get_speed(stmt, n1, n2)
            if isnothing(speed)
                this_edge_incomplete = true
                break
            else
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
                @error "Speeds do not match: expected $(round(expected_speed, digits=2)) kmh, found $(round(actual_speed, digits=2)) kmh, at edge containing nodes $nodes (distance $(round(sum_dists, digits=1))m)"
            end
        else
            missng += 1
        end
    end

    @info "$correct edges had correct speed information"
    @info "$incorrect edges had incorrect speed information"
    @info "$missng edges had missing speed information"

    println(histogram(speed_differences, title="Expected (StreetLight) - actual (OSRM) (kmh)", nbins=60, vertical=true))
    println("Minimum: $(round(minimum(speed_differences), sigdigits=3))")
    println("Maximum: $(round(maximum(speed_differences), sigdigits=3))")
    for pctile in [0.05, 0.5, 1, 2.5, 5, 25, 50, 75, 95, 97.5, 99, 99.5, 99.95]
        println("Percentile $pctile: $(round(percentile(speed_differences, pctile), sigdigits=3))")
    end
end

main(ARGS...)