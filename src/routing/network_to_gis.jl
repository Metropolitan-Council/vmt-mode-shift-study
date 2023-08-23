# This reads an OSRM network and converts it to a GIS file
# Currently needs the toolchain branch of OSRM.jl

using GeoDataFrames, ArchGDAL, ArgParse, Geodesy, ArchGDAL, Tables, GeoFormatTypes

import OSRM.Toolchain: OSRMToolchain, get_geometry

function main(raw_args)
    s = ArgParseSettings()
    @add_arg_table! s begin
        "network"
            help = "OSRM network"
        "output"
            help = "Output file"
        "--driver"
            help = "GDAL driver"
            default = "GPKG"
    end

    args = parse_args(raw_args, s)

    result = Vector{@NamedTuple{id::Int64, name::String, ref::String, lts::Int32, weight::Int32, duration::Int32, distance::Float32, oneway::Bool, speed_mph::Float64, geom::Any}}()

    toolchain::OSRMToolchain = OSRMToolchain(args["network"])

    # loop over all nodes
    for (i, node, weight, duration, distance) in zip(
            eachindex(toolchain.edge_based_nodes),
            toolchain.edge_based_nodes,
            toolchain.edge_based_node_weights,
            toolchain.edge_based_node_durations,
            toolchain.edge_based_node_distances
        )
        geom = ArchGDAL.createlinestring(map(x -> (x.lon, x.lat), get_geometry(toolchain, node)))

        ann = toolchain.edge_based_node_annotations[node.annotation_id + 1]
        lts = -1

        name = toolchain.names[ann.name_id ÷ 5 + 1]

        for (i, class) in enumerate(toolchain.class_names)
            if ann.class_data[i]
                if startswith(class, "lts")
                    # only one lts flag per edge, please
                    lts == -1 || error("Duplicate LTS!")
                    lts = parse(Int32, class[4])
                end
            end
        end
        
        # distance in meters, duration in deciseconds, convert to mph
        speed_mph = distance / (duration / 10) * 3600 / 1609

        push!(result, (id=i, name=something(name.name, ""), ref=something(name.ref, ""), lts=lts, weight=weight.weight, duration=duration,
            distance=distance, oneway=weight.oneway, speed_mph=speed_mph, geom=geom))
    end

    GeoDataFrames.write(args["output"], result; driver=args["driver"], geom_columns=(:geom,), crs=GeoFormatTypes.EPSG(4326))
end

main(ARGS)