using OSRM, ArgParse, Logging

s = ArgParseSettings()

@add_arg_table! s begin
    "network"
        help = "Path to OSRM network"
        required = true
end

# This runs testfunc with an OSRM instance loaded from command line argments
function run_tests(testfunc)
    args = parse_args(s)
    osrm = OSRMInstance(args["network"], "mld")
    testfunc(osrm)
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