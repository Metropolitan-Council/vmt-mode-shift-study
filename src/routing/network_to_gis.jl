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

    result = Vector{@NamedTuple{id::Int64, name::String, ref::String, lts::Int32, geom::Any}}()

    toolchain::OSRMToolchain = OSRMToolchain(args["network"])

    # loop over all nodes
    for (i, node) in enumerate(toolchain.edge_based_nodes)
        geom = ArchGDAL.createlinestring(map(x -> (x.lon, x.lat), get_geometry(toolchain, node)))

        ann = toolchain.edge_based_node_annotations[node.annotation_id + 1]
        lts = nothing

        name = toolchain.names[ann.name_id ÷ 5 + 1]

        for (i, class) in enumerate(toolchain.class_names)
            if ann.class_data[i]
                if startswith(class, "lts")
                    # only one lts flag per edge, please
                    isnothing(lts) || error("Duplicate LTS!")
                    lts = parse(Int32, class[4])
                end
            end
        end                 

        push!(result, (id=i, name=something(name.name, ""), ref=something(name.ref, ""), lts=lts, geom=geom))
    end

    GeoDataFrames.write(args["output"], result; driver=args["driver"], geom_columns=(:geom,), crs=GeoFormatTypes.EPSG(4326))
end

main(ARGS)