# This contains automated tests for the pedestrian network, to ensure the stress levels
# are applied correctly. Run it with the path to the network.

import OSRM.Toolchain: OSRMToolchain, get_node_ids
import OSRM: OSRMInstance, route
using Test, Geodesy

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

function main(network)
    toolchain = OSRMToolchain(network)
    it = IndexedToolchain(toolchain)

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

        
    end
end

main(ARGS[1])