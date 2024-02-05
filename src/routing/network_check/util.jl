using OSRM, ArgParse, Logging

s = ArgParseSettings()

@add_arg_table! s begin
    "network"
        help = "Path to OSRM network"
        required = true
end

# perform a route from origin to destination and return the OSM nodes traversed
function route_nodes(osrm, origin, destination, expected_nodes)
    routes = route(osrm, origin, destination)
    if isempty(routes)
        return nothing
    end

    length(routes) == 1 || error("Got multiple routes, expecting one")

    rte = first(routes)

    length(rte.legs) == 1 || error("Expecting exactly one leg")

    nodes = first(rte.legs).annotation.nodes

    if nodes == expected_nodes
        return true
    else
        # print some useful information about the result
        min_common_length = min(length(nodes), length(expected_nodes))
        diverge_start = findfirst(nodes[1:min_common_length] .!= expected_nodes[1:min_common_length])
        diverge_end = min_common_length - findfirst(reverse(nodes[1:min_common_length]) .!= reverse(expected_nodes[1:min_common_length])) + 1

        # https://discourse.julialang.org/t/string-builder-in-julia/17225
        errmsg = IOBuffer()
        println(errmsg, "Expected and routed paths not equal; they diverge between indices $diverge_start and $diverge_end")

        println(errmsg, "  Expected  Actual")
        for idx in diverge_start:diverge_end
            ex_pad = rpad(expected_nodes[idx], 11, " ")
            println(errmsg, "$ex_pad $(nodes[idx])")
        end

        if length(nodes) == length(expected_nodes)
            println(errmsg, "Length of nodes differ: expected $(length(expected_nodes)) nodes but found $(length(nodes)). Extra nodes:")
            extra_nodes = if length(nodes) < length(expected_nodes)
                expected_nodes[length(nodes) + 1:end]
            else
                nodes[length(expected_nodes) + 1:end]
            end

            println(errmsg, "\n".join(extra_nodes))
        end

        @error String(take!(errmsg))

        return false
    end
end


struct IndexedToolchain
    toolchain::OSRMToolchain
    index::Dict{NTuple{2, Int64}, Vector{Int64}}
end

function IndexedToolchain(toolchain)
    idx = Dict{NTuple{2, Int64}, Vector{Int64}}()
    for edge in eachindex(toolchain.edge_based_nodes)
        nodes = get_node_ids(toolchain, toolchain.edge_based_nodes[edge])
        from = first(nodes)
        to = last(nodes)
        if haskey(idx, (from, to))
            push!(idx[(from, to)], edge)
        else
            idx[(from, to)] = [edge]
        end
    end

    return IndexedToolchain(toolchain, idx)
end

"Find a edge-based node by origin and destination OSM nodes. Returns a vector as there may be multiple edges between a pair of nodes."
find_ebn(indexed_toolchain, from, to) = indexed_toolchain.index[(from, to)]

function get_lts(toolchain, ebnidx)
    lts = -1
    ann = toolchain.edge_based_node_annotations[toolchain.edge_based_nodes[ebnidx].annotation_id + 1]
    for (i, class) in enumerate(toolchain.class_names)
        if ann.class_data[i]
            if startswith(class, "lts")
                # only one lts flag per edge, please
                lts == -1 || error("Duplicate LTS!")
                lts = parse(Int64, class[4])
            end
        end
    end

    lts ≠ -1 || error("No LTS found!")

    return lts
end

function get_elev(rast, lat, lon)
    cell_size = 0.000092592593
    # we want to interpolate from pixel centers, hence the offset
    min_lon = -95.000555555994 + cell_size / 2
    min_lat = 41.999444440680 + cell_size / 2
    ncols = 32412
    nrows = 43212
    max_lon = min_lon + cell_size * (ncols - 1)
    max_lat = min_lat + cell_size * (nrows - 1)

    ystep = (max_lat - min_lat) / (nrows - 1)
    xstep = (max_lon - min_lon) / (ncols - 1)

    @assert xstep ≈ cell_size
    @assert ystep ≈ cell_size

    xth = (lon - min_lon) / xstep + 1
    yth = (max_lat - lat) / ystep + 1 # y points down

    left = floor(Int64, xth)
    right = ceil(Int64, xth)
    top = floor(Int64, yth)
    bottom = ceil(Int64, yth)

    fromLeft = xth % 1
    fromTop = yth % 1
    fromBottom = 1 - fromTop
    fromRight = 1 - fromLeft

    (rast[left, top] * (fromRight * fromBottom) +
                                      rast[right, top] * (fromLeft * fromBottom) +
                                      rast[left, bottom] * (fromRight * fromTop) +
                                      rast[right, bottom] * (fromLeft * fromTop)) * 1000
end

getspeedkmh(toolchain::OSRMToolchain, ebnidx) = toolchain.edge_based_node_distances[ebnidx] /
    (toolchain.edge_based_node_durations[ebnidx] / 10) * 3.6
    
function getspeedkmh(it::IndexedToolchain, fr, to)
    eidx = find_ebn(it, fr, to)
    length(eidx) == 1 || error("Did not find single edge for $fr to $to")
    getspeedkmh(it.toolchain, first(eidx))
end