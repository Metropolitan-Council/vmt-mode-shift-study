-- For long segments, split them into even parts as close to 10 meters as possible
SEGMENT_TARGET_LENGTH_METERS = 10

function load_elevation ()
    local ELEVATION_FILE = assert(os.getenv("ELEVATION_FILE"), "ELEVATION_FILE environment variable not specified!")
    local min_lon = -95.000555555994
    local min_lat = 41.999444440680
    local cell_size = 0.000092592593
    local ncols = 32412
    local nrows = 43212

    local raster_source = raster:load(
        ELEVATION_FILE,
        min_lon,
        min_lon + cell_size * ncols,
        min_lat,
        min_lat + cell_size * nrows,
        nrows,
        ncols
    )

    return raster_source
end

-- mark bridges and tunnels to remain flat
function mark_bridges_and_tunnels(profile, way, result, data)
    local tunnel = way:get_value_by_key("tunnel")
    local bridge = way:get_value_by_key("bridge")

    if (tunnel and tunnel ~= "no") or (bridge and bridge ~= "no") then
        result.is_startpoint = false
    end
end

function get_elevation_gain_mm (rasterData, source, target, distance)
     -- lua inexplicably has no round function: https://stackoverflow.com/questions/18313171
    local n_segments = math.max(math.floor(distance / SEGMENT_TARGET_LENGTH_METERS + 0.5), 1)
    local seg_frac = 1 / n_segments
    local seg_length = distance * seg_frac

    local elevation_gain_mm = 0

    for i = 1,n_segments,1 do
        local seg_start_frac = (i - 1) * seg_frac
        local seg_end_frac = i * seg_frac
        
        assert(seg_start_frac >= 0)
        assert(seg_start_frac < 1)
        assert(seg_end_frac > 0)
        assert(seg_end_frac <= 1)

        local origin_lon = source.lon + seg_start_frac * (target.lon - source.lon)
        local origin_lat = source.lat + seg_start_frac * (target.lat - source.lat)

        local dest_lon = source.lon + seg_end_frac * (target.lon - source.lon)
        local dest_lat = source.lat + seg_end_frac * (target.lat - source.lat)

        local origin_val = raster:interpolate(rasterData, origin_lon, origin_lat)
        local destination_val = raster:interpolate(rasterData, dest_lon, dest_lat)
        
        if origin_val.datum ~= origin_val.invalid_data() and destination_val.datum ~= destination_val.invalid_data() then

            -- print("origin elevation " .. origin_val.datum .. " meters, destination elevation " .. destination_val.datum .. "mm")

            -- * 1000 because seg_length is meters and elevations are millimeters
            local seg_elevation_mm = destination_val.datum - origin_val.datum
            local slope_pct = seg_elevation_mm / (seg_length * 1000) * 100

            if (slope_pct > 35 or slope_pct < -35) then
                print("Warning: street segment is steeper than Baldwin St in Dunedin, NZ (35%). Assuming bad data/no slope, at " .. origin_lat .. ", " .. origin_lon)
            else
                elevation_gain_mm = elevation_gain_mm + seg_elevation_mm
            end
        else
            if origin_val.datum == origin_val.invalid_data() then
                print("Data for source " .. origin_lat .. ", " .. origin_lon .. " is invalid: " .. origin_val.datum)
            end

            if destination_val.datum == destination_val.invalid_data() then
                print("Data for target " .. dest_lat .. ", " .. dest_lon .. " is invalid")
            end
        end
    end

    return elevation_gain_mm
end

function get_proportion_sloped_more_than (rasterData, source, target, distance, max_slope_pct)
    -- lua inexplicably has no round function: https://stackoverflow.com/questions/18313171
   local n_segments = math.max(math.floor(distance / SEGMENT_TARGET_LENGTH_METERS + 0.5), 1)
   local seg_frac = 1 / n_segments
   local seg_length = distance * seg_frac

   local elevation_gain_mm = 0

   local steep_segments = 0
   local total_segments = 0

   for i = 1,n_segments,1 do
       local seg_start_frac = (i - 1) * seg_frac
       local seg_end_frac = i * seg_frac
       
       assert(seg_start_frac >= 0)
       assert(seg_start_frac < 1)
       assert(seg_end_frac > 0)
       assert(seg_end_frac <= 1)

       local origin_lon = source.lon + seg_start_frac * (target.lon - source.lon)
       local origin_lat = source.lat + seg_start_frac * (target.lat - source.lat)

       local dest_lon = source.lon + seg_end_frac * (target.lon - source.lon)
       local dest_lat = source.lat + seg_end_frac * (target.lat - source.lat)

       local origin_val = raster:interpolate(rasterData, origin_lon, origin_lat)
       local destination_val = raster:interpolate(rasterData, dest_lon, dest_lat)
       
       assert(origin_val.datum ~= origin_val.invalid_data() and destination_val.datum ~= destination_val.invalid_data())

        -- print("origin elevation " .. origin_val.datum .. " meters, destination elevation " .. destination_val.datum .. "mm")

        -- * 1000 because seg_length is meters and elevations are millimeters
        local seg_elevation_mm = destination_val.datum - origin_val.datum
        local slope_pct = seg_elevation_mm / (seg_length * 1000) * 100

        if (slope_pct > 35 or slope_pct < -35) then
            print("Warning: street segment is steeper than Baldwin St in Dunedin, NZ (35%). Assuming bad data/no slope, at " .. origin_lat .. ", " .. origin_lon)
        elseif (slope_pct > max_slope_pct) then
            --print("origin elevation " .. origin_val.datum .. " mm, destination elevation " .. destination_val.datum .. "mm, segment length " .. seg_length .. "m, calculated slope " .. slope_pct .. " at " .. origin_lat .. ", " .. origin_lon)
            steep_segments = steep_segments + 1
        end

        total_segments = total_segments + 1
   end

   assert(total_segments == n_segments)

   return steep_segments / total_segments
end

