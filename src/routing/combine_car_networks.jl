# This script combines the car network .gpkg files together, so there is one
# network file that has speeds, etc. from each of the networks. This lets us
# compare networks directly

using ArgParse, GeoDataFrames, DataFrames, Logging

get_netname(fn) = match(r"^(.*?)(\.[a-zA-Z0-9]+)?$", basename(fn))[1]

function main(raw_args)
    s = ArgParseSettings()
    @add_arg_table! s begin
        "outfile"
        "infiles"
            nargs = '+'
        "--driver"
            help = "GDAL driver"
            default = "GPKG"
    end

    args = parse_args(raw_args, s)

    base, remain = Iterators.peel(args["infiles"])
    println(args["outfile"])

    @info "Processing $base"
    base_df = GeoDataFrames.read(base)
    rename!(base_df, :speed_mph => Symbol(get_netname(base) * "_speed_mph"))
    # Occasionally there are roads that are different with the same from and to nodes. These
    # are unlikely to be important in the network, so we drop one of them arbitrarily. This may
    # lead to spurious large changes if which one gets dropped is different in different networks
    unique!(base_df, [:fr_node, :to_node])

    for fn ∈ remain
        @info "Processing $fn"
        df = GeoDataFrames.read(fn)
        new_right = select(df, [:fr_node, :to_node, :speed_mph])
        rename!(new_right, :speed_mph => Symbol(get_netname(fn) * "_speed_mph"))
        unique!(new_right, [:fr_node, :to_node])
        leftjoin!(base_df, new_right, on=[:fr_node, :to_node])
    end

    GeoDataFrames.write(args["outfile"], base_df, driver=args["driver"], geom_columns=(:geom,))
end

main(ARGS)