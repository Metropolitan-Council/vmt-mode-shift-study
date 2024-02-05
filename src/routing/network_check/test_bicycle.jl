# This contains automated tests for the bicycle networks, to ensure the LTS and weighting
# are applied correctly. Run it with the path to the network.

import OSRM.Toolchain: OSRMToolchain, get_node_ids, get_geometry
import OSRM: OSRMInstance, route
using Test, Geodesy, Plots, StatsPlots, Rasters

include("util.jl")

function islts(indexed_toolchain, fr, to, lts)
    forward_edges = find_ebn(indexed_toolchain, fr, to)
    backward_edges = find_ebn(indexed_toolchain, to, fr)
    if isempty(forward_edges) && isempty(backward_edges)
        error("Edge from $fr to $to not found")
    elseif length(forward_edges) > 1 || length(backward_edges) > 1
        error("Found multiple edges from $fr to $to")
    else
        return get_lts(indexed_toolchain.toolchain, first(forward_edges)) == lts &&
        return get_lts(indexed_toolchain.toolchain, first(backward_edges)) == lts
    end 
end

function spot_check_lts_assignment(indexed_toolchain)
    @testset "LTS Assignment" begin
        # This contains tests that LTS values were assigned correctly
        # Numbered comments are copied from the AO source file: https://github.com/AccessibilityObservatory/AOBikeLTS/blob/main/LTS_assignment.py
        # and possibly slightly edited in situations where our profile differs from theirs intentionally
        # (frequently when they disallow a path entirely but we allow walking bikes).
        # amenity=parking is LTS 2 (perhaps it should be LTS 5 as service roads are LTS 5, for consistency)?
        # way 247964285
        @test islts(indexed_toolchain, 247964285, 247964283, 2)

        # highway=service should be LTS 5 (way 5995610). However, LTS 5 is just a special case
        # of LTS 4, so that is what it is coded as here. LTS 5 is LTS 4 but crossings do
        # not trigger an LTS 4 penalty. This is tested in the Beaudry Meadows Park test below.
        @test islts(indexed_toolchain, 34525950, 34667326, 4)
        @test getspeedkmh(indexed_toolchain, 34525950, 34667326) < 5

        #1 - footpaths/sidewalks that don't explicitly allow bicycles are low LTS but require dismount;
        # if no bicycle tag, assumes disallowed
        # highway=footway (way 6023334)
        @test islts(indexed_toolchain, 34394024, 9339424877, 1)
        # on footway, OSRM requires dismount
        @test getspeedkmh(indexed_toolchain, 34394024, 9339424877) < 5


        #2 - generic paths that don't explicitly disallow bicycles should be included as LTS 1 --
        # this commonly includes suburban bicycle paths around lakes
        # highway=path (way 1085436119)
        @test islts(indexed_toolchain, 4454086584, 9945862965, 1)
        @test getspeedkmh(indexed_toolchain, 4454086584, 9945862965) > 10

        #3 - generic paths that don't allow bicycles should require dismount but still be
        # LTS 1
        # way 166641792
        @test islts(indexed_toolchain, 431009691, 1780806449, 1)
        @test getspeedkmh(indexed_toolchain, 431009691, 1780806449) < 5

        # highway=footway, bicycle=no (way 101377263)
        # should still be LTS 1
        @test islts(indexed_toolchain, 945514931, 945514802, 1)
        @test getspeedkmh(indexed_toolchain, 945514931, 945514802) < 5

        # highway=pedestrian (way 579967558)
        @test islts(indexed_toolchain, 5553312364, 8355502554, 1)
        @test getspeedkmh(indexed_toolchain, 5553312364, 8355502554) < 5

        #4 - crossings that don't disallow bikes are LTS 1
        # no highway=crossing in the region

        #5 - footpaths/sidewalks that do explicitly allow bicycles should be LTS 1
        # highway=footway, bicycle=yes (way 39182243)
        # should still be LTS 1, but faster
        @test islts(indexed_toolchain, 187890109, 187890111, 1)
        @test getspeedkmh(indexed_toolchain, 187890109, 187890111) > 10

        # highway=footway, bicycle=designated
        # should still be LTS 1, but faster
        @test islts(indexed_toolchain, 469356694, 469356680, 1)
        @test getspeedkmh(indexed_toolchain, 469356694, 469356680) > 10

        # highway=pedestrian, bicycle=yes (way 753242378)
        @test islts(indexed_toolchain, 7038049451, 7038049456, 1)
        @test getspeedkmh(indexed_toolchain, 7038049451, 7038049456) > 10

        #6 - restricted-access facilities with bicycle designation should be LTS 2
        # restricted use (access=no bicycle=yes, way 136112910)
        @test islts(indexed_toolchain, 1493564733, 423733838, 2)
        @test getspeedkmh(indexed_toolchain, 1493564733, 423733838) > 10

        #7 - fully separated facilities, LTS 1 
        # highway=cycleway (way 380685978)
        @test islts(indexed_toolchain, 405081780, 6585416122, 1)
        @test getspeedkmh(indexed_toolchain, 405081780, 6585416122) > 10

        # cycleway=track (way 18062111)
        @test islts(indexed_toolchain, 1137030176, 1137030200, 1)
        @test getspeedkmh(indexed_toolchain, 1137030176, 1137030200) > 10

        # cycleway:right=track (way 37022473)
        # this is a contraflow bikeway
        @test islts(indexed_toolchain, 1856490419, 1125901889, 1)
        @test getspeedkmh(indexed_toolchain, 1856490419, 1125901889) > 10

        # cycleway:left=track (way 6039337)
        @test islts(indexed_toolchain, 8140383156, 8147830042, 1)
        @test getspeedkmh(indexed_toolchain, 8140383156, 8147830042) > 10

        # cycleway[:left, :right]=opposite_track
        # none in region

        # two-way cycleway (way 6011755)
        @test islts(indexed_toolchain, 33351569, 2390777505, 1)
        @test getspeedkmh(indexed_toolchain, 33351569, 2390777505) > 10
        @test getspeedkmh(indexed_toolchain, 2390777505, 33351569) > 10

        # contraflow cycleway. OSM tags are not good enough to reliably determine directions, so we
        # assume LTS is 1 when there is a cycle track in either direction (way 6012675)
        @test islts(indexed_toolchain, 33799614, 2591603175, 1)
        @test getspeedkmh(indexed_toolchain, 33799614, 2591603175) > 10
        # should be edges in both directions
        @test haskey(indexed_toolchain.index, (33799614, 2591603175))
        @test haskey(indexed_toolchain.index, (2591603175, 33799614))

        #8 shared busways, LTS 2
        # Shared busways: LTS 2 (way 1042541943)
        @test islts(indexed_toolchain, 8359454336, 8359454340, 2)
        @test getspeedkmh(indexed_toolchain, 8359454336, 8359454340) > 10

        # cycleway:right=share_busway (way 18219762)
        @test islts(indexed_toolchain, 2097221266, 2091677244, 2)
        @test getspeedkmh(indexed_toolchain, 2097221266, 2091677244) > 10

        # no cycleway:left=share_busway in region

        #9 low-speed shared lanes, LTS 2
        # low speed shared lanes (note that this is based on OSM speeds not Streetlight speeds - way 636383764)
        @test islts(indexed_toolchain, 33418345, 9533219870, 2)
        @test getspeedkmh(indexed_toolchain, 33418345, 9533219870) > 10

        # tagged as cycleway:left=shared_lane
        # way 6038532
        # note that this also has cycleway:right=lane, but in our methodology and the original AO methodology,
        # shared lanes are processed before non-shared lanes, so the shared-lane-based LTS prevails.
        # See routing errata.
        @test islts(indexed_toolchain, 33420991, 7262523016, 2)
        @test getspeedkmh(indexed_toolchain, 33420991, 7262523016) > 10

        # cycleway:right=shared
        # way 40723313
        @test islts(indexed_toolchain, 494766110, 494766119, 2)
        @test getspeedkmh(indexed_toolchain, 494766110, 494766119) > 10

        # higher-speed non-residential shared lanes
        # this rule does not handle :left/:right (see errata) but the effect is minimal
        # as these streets likely will be LTS 3 anyhow (unless they have bike lanes)
        # way 18302382
        @test islts(indexed_toolchain, 8175777357, 188527890, 3)

        # non residential shared lanes without speed information (way 5996489)
        @test islts(indexed_toolchain, 34391121, 34652067, 3)
        @test getspeedkmh(indexed_toolchain, 34391121, 34652067) < 5

        # High speed residential shared lanes are LTS 1. I don't know that this
        # is the best thing, but it is what the Acessibility Observatory did, and it only affects
        # a handful of streets - from rule #20 - highway = residential or living_street, LTS 1
        # Way 668550677
        @test islts(indexed_toolchain, 9301614122, 188543197, 1)
        @test getspeedkmh(indexed_toolchain, 9301614122, 188543197) > 10

        # Bike lane logic
        # If there is a bike lane, and we know the number of lanes and the speed, we use the following logic
        # Number of lanes:  1    2    3+
        # Speed: <= 25 mph  1    2    3  
        #        <= 30 mph  2    3    3
        #        <= 35 mph  3    3    3
        #         > 35 mph  3    3    4

  		#11-19 different cases of on-street bike lanes

        # 11-13: 0 < lanes_each_way < 2 and
        begin
            # 11:  0 < maxspeed <= 25:
            # Way 6003800: 25 mph, 1 lane each way, bike lane
            @test islts(indexed_toolchain, 34162637, 711326285, 1)
            @test getspeedkmh(indexed_toolchain, 34162637, 711326285) > 10

            # 12: 0 < maxspeed <= 30
            # Way 6015263: 30 mph, one lane each way, bike lane
            @test islts(indexed_toolchain, 8807695001, 8807694977, 2)
            @test getspeedkmh(indexed_toolchain, 8807695001, 8807694977) > 10

            # 13: maxspeed > 30
            # Way 118353109: 35 mph, one lane each way, bike lane
            @test islts(indexed_toolchain, 34538632, 34398041, 3)
            @test getspeedkmh(indexed_toolchain, 34538632, 34398041) < 5

            # Way 18011446: 45 mph, one lane each way, bike lane
            @test islts(indexed_toolchain, 8266613929, 186269967, 3)
            @test getspeedkmh(indexed_toolchain, 8266613929, 186269967) < 10
        end
        
        # 14-15: lanes_each_way == 2
        begin
            # 14: 0 < maxspeed <= 25
            # Way 37022469: 25 mph, one way, two lanes, bike lane
            # it should be LTS 2 in both directions, but slow in one direction because you have to walk against traffic
            @test islts(indexed_toolchain, 430581449, 7506044466, 2)
            @test getspeedkmh(indexed_toolchain, 430581449, 7506044466) > 10 # forward
            @test islts(indexed_toolchain, 7506044466, 430581449, 2)
            @test getspeedkmh(indexed_toolchain, 7506044466, 430581449) < 10 # reverse

            # 15: maxspeed > 25
            # Way 179313477: 30 mph, two lanes each way, bike lane
            @test islts(indexed_toolchain, 4844779938, 4840647030, 3)
            @test getspeedkmh(indexed_toolchain, 4844779938, 4840647030) < 10

            # Way 1073052908, 35 mph, two lanes each way bike lane
            @test islts(indexed_toolchain, 34514532, 6856755193, 3)
        end

        # 16-17: lanes each way > 2
        begin
            # 16: maxspeed <= 35
            # way 720899812: 30 mph, three lanes, one way
            @test islts(indexed_toolchain, 6763975471, 6763975465, 3)

            # 17: maxspeed > 35
            # Way 1036273651: 40 mph, four lanes, one way, bike lane
            # This way gets merged with 125701109 because they are both LTS 4
            @test islts(indexed_toolchain, 9547239284, 1895646173, 4)
            @test getspeedkmh(indexed_toolchain, 9547239284, 1895646173) < 10
        end

        # 18-19: Insufficient speed/lane configuration information
        begin
            # 18: tags.get('highway','') in ['unclassified', 'tertiary', 'tertiary_link']
            # and we add residential
            # way 18015704: unclassified, 2 lanes, no speed info
            @test islts(indexed_toolchain, 186213493, 186163419, 2)

            # way 6009340: tertiary, no lane or speed info
            @test islts(indexed_toolchain, 33358026, 33551185, 2)

            # way 880362621: tertiary_link, no lane/speed info
            @test islts(indexed_toolchain, 5887726900, 33635768, 2)

            # way 6034134: residential, speed but no lane info
            @test islts(indexed_toolchain, 33424199, 6828103773, 2)

            # 19: otherwise
            # way 639492443: primary, no speed/lane info
            @test islts(indexed_toolchain, 582111855, 3699934694, 3)
        end

        # Different ways to specify bike lanes
        # no cycleway=opposite_lane
        begin
            # cycleway:left=lane
            # way 6036968, tertiary, 25mph, 3 lanes one way
            # NB this would be LTS 2 without a bike lane
            @test islts(indexed_toolchain, 33420880, 4161907999, 3)

            # cycleway:left=opposite_lane
            # way 6000479, 20 mph, no lane info
            @test islts(indexed_toolchain, 34524298, 8361593130, 1)

            # cycleway:right=lane
            # way 5994406, 30 ph, 3 lanes one way
            @test islts(indexed_toolchain, 33307818, 3051927246, 3)

            # no cycleway:right=opposite_lane
        end

        # Contraflow lanes: Way 6000479 is one way but has a contraflow bike lane
        @test islts(indexed_toolchain, 34524298, 8361593130, 1)
        @test getspeedkmh(indexed_toolchain, 34524298, 8361593130) > 10
        @test getspeedkmh(indexed_toolchain, 8361593130, 34524298) > 10

        #20 - highway = residential or living_street, LTS 1
        # way 114498295, highway=residential
        @test islts(indexed_toolchain, 34545155, 34566355, 1)

        # way 6035940: highway=living_street
        @test islts(indexed_toolchain, 33369210, 33369312, 1)

        #21 - small & slow (under 3 lanes & maxspeed <= 25), LTS 2
        # way 6017167 - speed 25 mph, 2 lanes
        @test islts(indexed_toolchain, 33550991, 33394437, 2)

        #22 -- slow but more than 3 lanes, LTS 3 -- informed by PFB
        # way 125438252
        @test islts(indexed_toolchain, 33348772, 9246839144, 3)

        #23 - slow and lanes not specified, LTS 2
        # way 762955075
        @test islts(indexed_toolchain, 187936284, 2689282794, 2)

        #24 - highway = tertiary & no assignment yet (built in), LTS 3
        # way 6037799
        @test islts(indexed_toolchain, 34540941, 5012476087, 3)

        #25 - highway = tertiary_link or unclassified & no assignment yet (built in), LTS 2
        # way 180774905, tertiary_link
        @test islts(indexed_toolchain, 1912414860, 34536825, 2)

        # way 6024228, unclassified
        @test islts(indexed_toolchain, 5971319029, 33493274, 2)

        #26 - highway = primary, trunk, primary_link, trunk_link, & no assignment yet (no separated facilities), LTS 4
        # way 39610423 - primary
        @test islts(indexed_toolchain, 474820501, 474820509, 4)

        # way 132091334 - primary_link
        @test islts(indexed_toolchain, 2685281710, 187909225, 4)

        # OSRM does not route on trunk and trunk_link unless explicitly tagged

		#27 - catch-all, if we reach this point with no assignment, LTS 4
        # way 6033734
        @test islts(indexed_toolchain, 34667830, 1815492864, 4)
    end
end

"This function is a place to check entire routes to make sure they take the expected path"
function spot_check_routing(osrm)
    @testset "Beaudry Meadows Park" begin
        # This is a route near Beaudry Meadows Park in Albertville
        # A trip along 77th St from Lamont Ave to Large Ave incorrectly deviated north to 70th St via the
        # Lancaster Ave sidewalk, to avoid crossing a highway=service link with a high LTS.
        # Service roads should definitely not discourage crossing. We have corrected this by assigning service roads LTS
        # 5, which is like LTS 4 but does not impose crossing penalties.

        @test route_nodes(osrm, LatLon(45.2622784, -93.6572516), LatLon(45.2634825, -93.6529270), [
            1996506443,
            5402303219,
            1813232814,
            5396345618,
            5396345617,
            1996506391,
            5396345616,
            5396345615,
            5396345614,
            1813232822,
            5396345613,
            5396345612,
            5396345611,
            5402303242,
            1813233258,
            5396345610,
            5402303245,
            1813232816,
            5396345609,
            5402303273,
            1813232815,
            5396345608
        ])
    end
end

function plot_weights_by_lts(toolchain)
    lts = get_lts.(Ref(toolchain), eachindex(toolchain.edge_based_nodes))
    weight_per_meter = getproperty.(toolchain.edge_based_node_weights, :weight) ./ toolchain.edge_based_node_distances
    sel = toolchain.edge_based_node_distances .> 0.1

    violin(lts[sel], weight_per_meter[sel])
    Plots.xlabel!("Level of Traffic Stress")
    Plots.ylabel!("Weight per meter")
    Plots.savefig("lts_weights.svg")
end

function plot_weights_by_elevation(toolchain, elev_file)
    raster = Raster(elev_file)
    
    weight_per_meter = Float64[]
    elev_gains_m = Float64[]
    eids = Int64[]

    for (eidx, ebn) in pairs(toolchain.edge_based_nodes)
        if eidx % 10000 == 0
            @info "Processed $eidx edges"
        end

        # only applying to LTS 1/2 as 3/4 uses walking profile
        if get_lts(toolchain, eidx) <= 2
            elev_gain_m = zero(Float64)
            incomplete = false

            geom = get_geometry(toolchain, ebn)::Vector{LatLon{Float64}}
            for (p1, p2) in zip(geom[1:end-1], geom[2:end])
                start_elev_mm = get_elev(raster, p1.lat, p1.lon)
                end_elev_mm = get_elev(raster, p2.lat, p2.lon)
                slope_pct = (end_elev_mm - start_elev_mm) / 1000 / euclidean_distance(p1, p2) * 100

                @assert !isnothing(start_elev_mm) && !isnothing(end_elev_mm)
                
                # slopes over 35% are ignored as likely bad data
                if end_elev_mm > start_elev_mm && slope_pct < 35
                    elev_gain_m += (end_elev_mm - start_elev_mm) / 1000
                end
            end

            push!(weight_per_meter, toolchain.edge_based_node_weights[eidx].weight / toolchain.edge_based_node_distances[eidx])
            push!(elev_gains_m, elev_gain_m / toolchain.edge_based_node_distances[eidx])
            push!(eids, eidx)
        end
    end

    sel = toolchain.edge_based_node_distances[eids] .> 0.5
    Plots.scatter(elev_gains_m[sel], weight_per_meter[sel], markersize=0.1, markeralpha=0.15, format=:png)
    Plots.ylims!(0, 20)
    Plots.xlims!(0, 0.35)
    Plots.xlabel!("Elevation gain (meters) per horizontal meter, link-level average")
    Plots.ylabel!("Weight per horizontal meter (unitless)")
    Plots.savefig("elevation_check_bike.png")
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
    indexed_toolchain = IndexedToolchain(toolchain)
    osrm = OSRMInstance(args["network"], "mld")

    spot_check_lts_assignment(indexed_toolchain)
    spot_check_routing(osrm)
    plot_weights_by_lts(toolchain)
    plot_weights_by_elevation(toolchain, args["elevation"])
end

main(ARGS)