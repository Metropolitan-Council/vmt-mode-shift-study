# This contains automated tests for the pedestrian network. It contains the following tests
# - It spot-checks a number of edges (one in each category) to ensure they are assigned the correct pedestrian stress
# - It plots the weight by pedestrian quality, to ensure that weights increase as quality decreases, and saves the result to
#   ped_quality_weights.svg
# - It checks the weight per meter of every edge to ensure it is consistent with the elevation changes, and plots the weight per meter
#   as a function of elevation to ped_elevation_weights.svg

import OSRM.Toolchain: OSRMToolchain, get_node_ids, get_geometry
import OSRM: OSRMInstance, route
using Test, Geodesy, Plots, StatsPlots, ArgParse, Rasters
import CategoricalArrays: cut

include("util.jl")

# get the pedestrian quality for a particular edge
function get_ped_qual(toolchain::OSRMToolchain, ebnidx)
    pedqual = nothing
    ann = toolchain.edge_based_node_annotations[toolchain.edge_based_nodes[ebnidx].annotation_id + 1]
    for (i, class) in enumerate(toolchain.class_names)
        if ann.class_data[i]
            if startswith(class, "pedqual")
                # only one lts flag per edge, please
                isnothing(pedqual) || error("Duplicate LTS!")
                pedqual = class[8:end]
            end
        end
    end

    return pedqual
end

# find an edge from fr to to and get the ped quality
function get_ped_qual(indexed_toolchain, fr, to)
    forward_edges = find_ebn(indexed_toolchain, fr, to)
    backward_edges = find_ebn(indexed_toolchain, to, fr)
    if isempty(forward_edges) && isempty(backward_edges)
        error("Edge from $fr to $to not found")
    elseif length(forward_edges) > 1 || length(backward_edges) > 1
        error("Found multiple edges from $fr to $to")
    else
        fwdq = get_ped_qual(indexed_toolchain.toolchain, first(forward_edges))
        revq = get_ped_qual(indexed_toolchain.toolchain, first(backward_edges))
        fwdq == revq || error("Quality not the same in both directions at way from $fr to $to")
        return fwdq
    end 
end

function spot_check_quality_assignment(toolchain)
    @testset "Ped quality assignment" begin
        ##################
        ## HAS SIDEWALK ##
        ##################

        # More than 55 mph - none in the region

        # Less than 55 mph, 6 or more lanes
        # S Robert St in Saint Paul, Way 637912105
        @test get_ped_qual(it, 652981847, 652981846) == "low"

        #### 4-5 LANES

        # Less than 55 mph, 4--5 lanes, primary
        # Arcade St/US 61 in Ramsey, Way 40662565
        @test get_ped_qual(it, 493883041, 187928893) == "low"

        # 41-55 mph, 4--5 lanes, minor
        # None in region

        # <= 40 mph, 4-5 lanes, minor
        # Lake Road, Woodbury, way 18298253
        @test get_ped_qual(it, 188522967, 2674132674) == "medium"

        # 4-5 lanes, local
        # none in the region

        #### <= 3 LANES

        # 31-55 mph, major
        # 7 St W in St Paul, way 199132310
        @test get_ped_qual(it, 1488051397, 3060790330) == "low"

        # <= 30 mph, major
        # Snelling Ave S in St Paul, way 931208470
        # This is a 3 lane each way divided highway, but mapped as two three-lane one-way roads
        @test get_ped_qual(it, 187909630, 8403165281) == "medium"

        # 41-55 mph, minor
        # Cliff Rd, way 113586794
        @test get_ped_qual(it, 1287939732, 1287939738) == "low"

        # <= 40 mph, minor
        # Bailey Rd, way 163350414
        @test get_ped_qual(it, 541766100, 592447789) == "medium"

        # 41-55 mph, <= 3 lanes, local
        # Saint Olaf Ave W, Northfield, way 18228216
        @test get_ped_qual(it, 2071191885, 187996975) == "low"

        # 31-40 mph, local
        # Autumn Path, way 51297556
        @test get_ped_qual(it, 10236586469, 10236586466) == "medium"

        # <= 30 mph, local
        # 36th St, way 18076326
        @test get_ped_qual(it, 186770812, 186754875) == "high"

        #################
        ## NO SIDEWALK ##
        #################

        # 4+ lanes
        # East 46th St, Way 6019046 (note there are sidewalks here but mapped separately)
        @test get_ped_qual(it, 34180435, 7412665279) == "avail"

        # 3 lanes, 31+ mph
        # CR 62, way 759875981 has no maxspeed specified but is primary so defaults to 40 mph
        @test get_ped_qual(it, 2394569868, 4931397186) == "avail"

        # Freeway: none where peds are allowed

        # Major arterial, no lanes specified so defaults to 2, speed 30 mph
        # Robert Trail S / Hiawatha Pioneer Trl, way 640423083
        @test get_ped_qual(it, 7411553589, 3631626278) == "medium"

        # Minor arterial, speed <= 30
        # Lake St, Way 6013426
        @test get_ped_qual(it, 34164858, 34499020) == "medium"

        # Local, speed <= 30
        # 48th Pl N, way 5997983
        @test get_ped_qual(it, 33798890, 34508223) == "medium"

        ################
        ## OFF STREET ##
        ################

        # footway, way 183938393
        @test get_ped_qual(it, 1943750611, 1943750614) == "high"

        # cycleway, way 35090906
        @test get_ped_qual(it, 248125876, 1735876478) == "high"
    end
end

function plot_weights_by_quality(toolchain)
    # ensure weights vary correctly by ped stress by plotting
    # this won't be perfect due to rounding, elevation, surface penalties, etc.,
    # but should look pretty good

    pedquality = get_ped_qual.(Ref(toolchain), eachindex(toolchain.edge_based_nodes))
    weight_per_meter = getproperty.(toolchain.edge_based_node_weights, :weight) ./ toolchain.edge_based_node_distances
    sel = toolchain.edge_based_node_distances .> 0.1

    violin(pedquality[sel], weight_per_meter[sel])
    Plots.xlabel!("Pedestrian quality")
    Plots.ylabel!("Weight per meter")
    Plots.savefig("ped_quality_weights.svg")
end

function plot_weights_by_elevation(toolchain, elevation_file)
    raster = Raster(elevation_file);
    weight_per_meter = Float64[]
    percent_steep = Float64[]
    eids = Int64[]
    
    for (eidx, ebn) in pairs(toolchain.edge_based_nodes)
        if eidx % 10000 == 0
            @info "Processed $eidx edges"
        end
    
        steep_dist = zero(Float64)
    
        geom = get_geometry(toolchain, ebn)::Vector{LatLon{Float64}}
        for (p1, p2) in zip(geom[1:end-1], geom[2:end])
            dist = euclidean_distance(p1, p2)
            n_segments = max(round(Int64, dist / 10), 1)
            steep_segments = 0
    
            Δlat = p2.lat - p1.lat
            Δlon = p2.lon - p1.lon
    
            for segment in 1:n_segments
                orig_frac = (segment - 1) / n_segments
                dest_frac = segment / n_segments
                start_elev_mm = get_elev(raster, p1.lat + orig_frac * Δlat, p1.lon + orig_frac * Δlon)
                end_elev_mm = get_elev(raster, p1.lat + dest_frac * Δlat, p1.lon + dest_frac * Δlon)
    
                @assert !isnothing(start_elev_mm) && !isnothing(end_elev_mm)
                if end_elev_mm > start_elev_mm
                    slope_pct = (end_elev_mm - start_elev_mm) / 1000 / euclidean_distance(p1, p2) * 100
                    if slope_pct > 10 && slope_pct < 35
                        steep_segments += 1
                    end
                end
            end
    
            steep_dist += steep_segments / n_segments * dist
        end
    
        push!(weight_per_meter, toolchain.edge_based_node_weights[eidx].weight / toolchain.edge_based_node_distances[eidx])
        push!(percent_steep, steep_dist / toolchain.edge_based_node_distances[eidx] * 100)
        push!(eids, eidx)
    end

    sel = toolchain.edge_based_node_distances[eids] .> 0.5
    percent_steep_binned = cut(min.(percent_steep[sel], 99.99), 0:10:100)
    violin(percent_steep_binned, weight_per_meter[sel])

    Plots.xlabel!("Percent with grade >10%")
    Plots.ylabel!("Weight per meter")
    Plots.savefig("ped_elevation_weights.svg")
end

function main(raw_args)
    s = ArgParseSettings()

    @add_arg_table! s begin
        "network"
            help = "OSRM network to use"
        "elevation"
            help = "Path to the combined.tif file containing elevation"
    end

    args = parse_args(raw_args, s)

    toolchain = OSRMToolchain(args["network"])
    it = IndexedToolchain(toolchain)

    spot_check_quality_assignment(it)
    plot_weights_by_quality(toolchain)
    plot_weights_by_elevation(toolchain, args["elevation"])
end

main(ARGS)