# This script processes an OSM file and extracts all unique highway tags, and writes them out as a CSV
# Usage: julia --project extract_highway_tags.jl path/to/analysis-area.pbf path-to-output.csv
# Then edit the CSV file to include the speeds, and run area_for_way.jl
# This takes about a minute to run

using CSV, DataFrames, OpenStreetMapPBF, Logging


function main(infile, outfile)
    highway_tags = Set{String}()

    i = 0

    scan_ways(infile) do way
        i += 1

        if i % 100000 == 0
            @info "Processed $i ways"
        end

        if haskey(way.tags, "highway")
            push!(highway_tags, way.tags["highway"])
        end
    end

    df = DataFrame("tag"=>sort(collect(highway_tags)), "class"=>"")

    CSV.write(outfile, df)
end

main(ARGS[1], ARGS[2])