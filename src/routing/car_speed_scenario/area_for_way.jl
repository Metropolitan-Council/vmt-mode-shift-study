# This script processes an OSM file and extracts all unique highway tags, and writes them out as an SQLite database

using CSV, DataFrames, OpenStreetMapPBF, Logging, EnumX, GeoDataFrames, DBInterface, SQLite, LibSpatialIndex, ArchGDAL
import GeoFormatTypes as GFT

@enumx AreaType Urban Suburban Rural Unknown

const UTM = GFT.EPSG(26915)
const WGS84 = GFT.EPSG(4326)

const SPEEDS_MPH = Dict{Tuple{String, AreaType.T}, Int64}(
    ("shared", AreaType.Urban) => 10,
    ("shared", AreaType.Suburban) => 10,
    ("shared", AreaType.Rural) => 10,
    ("minor", AreaType.Urban) => 20,
    ("minor", AreaType.Suburban) => 20,
    ("minor", AreaType.Rural) => 20,
    ("major", AreaType.Urban) => 25,
    ("major", AreaType.Suburban) => 35,
    ("major", AreaType.Rural) => 35,
    ("freeway", AreaType.Urban) => 55,
    ("freeway", AreaType.Suburban) => 55,
    ("freeway", AreaType.Rural) => 65
)

function main(infile, shapefile, outfile)
    if isfile(outfile)
        error("Outfile already exists!")
    end

    # node ids on highways
    highway_node_ids = Set{Int64}()

    # number of ways
    n_ways = 0

    road_classification_df = CSV.read(joinpath(Base.source_dir(), "highway_types.csv"), DataFrame)
    road_classification = Dict{String, String}(road_classification_df.tag .=> road_classification_df.class)

    @info "Pass 1: extracting highway nodes"
    scan_ways(infile) do way
        if haskey(way.tags, "highway") && haskey(road_classification, way.tags["highway"])
            n_ways += 1
            union!(highway_node_ids, way.nodes)
        end
    end

    # I'm not sure if we can store arbitrary 64-bit ints in a spatial index, so index them
    # sequentially.
    highway_node_vector = Int64[]
    sizehint!(highway_node_vector, length(highway_node_ids))

    @info "Pass 2: reading nodes and building spatial index"
    nodes_read = 0
    nodes = Dict{Int64, ArchGDAL.IGeometry{ArchGDAL.wkbPoint}}()
    node_idx = LibSpatialIndex.RTree(2)
    scan_nodes(infile) do node
        if node.id ∈ highway_node_ids
            push!(highway_node_vector, node.id)
            LibSpatialIndex.insert!(node_idx, length(highway_node_vector), [node.lon, node.lat], [node.lon, node.lat])
            nodes[node.id] = ArchGDAL.createpoint(node.lon, node.lat)
            nodes_read += 1
            if nodes_read % 100_000 == 0
                @info "Read $nodes_read / $(length(highway_node_ids)) nodes ($(round(nodes_read / length(highway_node_ids) * 100, digits=1))%)"
            end
        end
    end

    @info "Reading shapefile and categorizing nodes"
    # For each highway node, whether it is in the urban area
    node_area = Dict{Int64, AreaType.T}()
    areas = GeoDataFrames.read(shapefile)
    # use lon/lat order https://discourse.julialang.org/t/archgdal-transforming-crs-incorrectly-probably-wrong-long-lat-order/90098
    areas.geom = GeoDataFrames.reproject(areas.geom, UTM, WGS84, order=:trad)

    for (i, geom, areacode) in zip(1:nrow(areas), areas.geom, areas.COMDESNAME)
        atype = if areacode ∈ ["Urban", "Urban Center"]
            AreaType.Urban
        elseif areacode ∈ ["Suburban", "Suburban Edge", "Emerging Suburban Edge"]
            AreaType.Suburban
        elseif areacode ∈ ["Agricultural", "Diversified Rural", "Non-Council Area", "Rural Center", "Rural Residential"]
            AreaType.Rural
        else
            # the list of area types above should be collectively exhaustive
            error("Unrecognized area type $areacode")
        end

        bbox = ArchGDAL.envelope(geom)
        # use spatial index to find nodes potentially in the area
        candidate_nodes = getindex.(Ref(highway_node_vector), LibSpatialIndex.intersects(node_idx, [bbox.MinX, bbox.MinY], [bbox.MaxX, bbox.MaxY]))

        for node in candidate_nodes
            # spatial index overselects
            if ArchGDAL.contains(geom, nodes[node])
                if !haskey(node_area, node)
                    node_area[node] = atype
                else
                    error("Node $node matches multiple areas!")
                end
            end
        end

        if i % 10 == 0
            @info "Processed $i / $(nrow(areas)) areas"
        end
    end

    @info "Categorized $(length(node_area)) nodes"

    @info "Pass 3: categorize ways"
    outdb = SQLite.DB(outfile)

    DBInterface.execute(outdb, "CREATE TABLE way_speeds (way_id int8 PRIMARY KEY, area_type VARCHAR, road_class VARCHAR, highway VARCHAR, speed_cap_mph int2)")
    stmt = DBInterface.prepare(outdb, "INSERT INTO way_speeds VALUES(:way_id, :area_type, :road_class, :highway, :speed_cap_mph)")

    SQLite.transaction(outdb)

    ways_processed = 0
    scan_ways(infile) do way
        if haskey(way.tags, "highway") && haskey(road_classification, way.tags["highway"])
            # figure out the speed
            rclass = road_classification[way.tags["highway"]]
            areas = [haskey(node_area, node_id) ? node_area[node_id] : AreaType.Unknown for node_id in way.nodes]

            # assign to the densest area the way passes through
            atype = if any(areas .== AreaType.Urban)
                AreaType.Urban
            elseif any(areas .== AreaType.Suburban)
                AreaType.Suburban
            elseif any(areas .== AreaType.Rural)
                AreaType.Rural
            else
                @warn "Way ID $(way.id) did not match any area types, assuming rural"
                AreaType.Rural
            end

            speed = SPEEDS_MPH[(rclass, atype)]
            DBInterface.execute(stmt, way_id=way.id, area_type=string(atype), road_class=rclass, highway=way.tags["highway"], speed_cap_mph=speed)

            ways_processed += 1

            if ways_processed % 100000 == 0
                @info "Processed $ways_processed / $n_ways ways ($(round(way_processed / n_ways * 100, digits=1))%)"
            end
        end
    end

    SQLite.commit(outdb)

    @info "Vacuuming"
    DBInterface.execute(outdb, "VACUUM")
    DBInterface.close!(outdb)
end

main(ARGS[1], ARGS[2], ARGS[3])