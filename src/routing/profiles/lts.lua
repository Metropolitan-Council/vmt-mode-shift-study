Tags = require("lualib/tags")

local LTS = {}

-- calculate LTS using Access Across America methodology
-- reference implementation: https://github.com/AccessibilityObservatory/AOBikeLTS/blob/main/LTS_assignment.py#L171
function LTS.lts_for_way(profile, way)
  local highway = way:get_value_by_key("highway")
  
  if not highway then
    -- handle things like parking lots, etc. These are not in the AO algorithm.
    -- Parking lots: LTS 2
    if way:get_value_by_key("amenity") == "parking" then return 2 end
  end

  -- Subtract 0.5 mph to account for floating point issues, in case unit
  -- conversions are not exact
  local maxspeed = LTS.get_ltsspeed(way, profile, false)
  local maxspeed_mph
  if maxspeed then
    maxspeed_mph = maxspeed / 1.609 - 0.5
  else
    maxspeed_mph = nil
  end

  local lanes_fwd, lanes_bwd = LTS.get_lanes(way, profile, false)
  local lanes_each_way = ((lanes_fwd and lanes_bwd) and math.max(lanes_fwd, lanes_bwd)) or nil

  local lanes_total = ((lanes_fwd and lanes_bwd) and lanes_fwd + lanes_bwd) or nil
  
  -- TODO a bunch of stuff disallowed by the methodology - OSRM should handle most of this already
  -- audit.

  -- generic paths that don't disallow bicycles
  if highway == "path" then return 1 end

  -- crossings are LTS 1
  if highway == "crossing" then return 1 end

  -- footpaths are LTS 1
  if highway == "footway" or highway == "pedestrian" then return 1 end

  -- restricted access facilities that allow bikes (allow bikes taken care of by OSRM)
  -- TODO AAA codes this as 2, but shouldn't it really be 1?
  if way:get_value_by_key("access") == "no" then return 2 end

  -- service roads - special LTS 5 value - equivalent to LTS 4 as in AAA, but doesn't
  -- bleed over to crossings
  if highway == "service" then return 5 end

  -- separated cycletracks
  -- TODO handle situations where there is only a cycle track in one direction of a two-way street (possibly contraflow)
  -- moreover, LTS may be different forwards and backwards
  local cycleway = way:get_value_by_key("cycleway")
  local cycleway_left = way:get_value_by_key("cycleway:left")
  local cycleway_right = way:get_value_by_key("cycleway:right")
  if highway == "cycleway" or cycleway == "track" or cycleway_left == "track" or
    cycleway_right == "track" or cycleway == "opposite_track" or cycleway_left == "opposite_track" or cycleway_right == "opposite_track" then
      -- TODO cycleway:left=opposite_track etc
      return 1
  end

  -- shared busways
  if cycleway == "share_busway" or cycleway == "opposite_share_busway" or 
    cycleway_left == "share_busway" or cycleway_left == "opposite_share_busway"
    cycleway_right == "share_busway" or cycleway_right == "opposite_share_busway" then return 2 end

  -- low speed shared lanes
  if (cycleway == "shared_lane" or cycleway_right == "shared_lane" or cycleway_left == "shared_lane") and maxspeed and maxspeed_mph <= 25 then return 2 end

  -- higher speed, non-residential shared lanes
  -- TODO what about residential high-speed shared lanes? seems to not be covered in the LTS methodology
  if cycleway == "shared_lane" and highway ~= "residential" then return 3 end

  if cycleway == "lane" or cycleway_right == "lane" or cycleway_left == "lane" or
    cycleway == "opposite_lane" or cycleway_right == "opposite_lane" or cycleway_left == "opposite_lane" then
      assert(lanes_each_way == nil or lanes_each_way > 0, lanes_each_way and "invalid lanes_each_way value " .. lanes_each_way .. " at way " .. way:id())
      assert(maxspeed_mph == nil or maxspeed_mph > 0, maxspeed_mph and "invalid maxspeed parsed as " .. maxspeed_mph .. " at way " .. way:id())
      if lanes_each_way and lanes_each_way < 2 then
        if maxspeed_mph and maxspeed_mph <= 25 then return 1
        elseif maxspeed_mph and maxspeed_mph <= 30 then return 2
        elseif maxspeed_mph and maxspeed_mph > 30 then return 3 end
      elseif lanes_each_way and lanes_each_way == 2 then
        if maxspeed_mph and maxspeed_mph <= 25 then return 2
        elseif maxspeed_mph and maxspeed_mph > 25 then return 3 end
      elseif lanes_each_way and lanes_each_way > 2 then
        if maxspeed_mph and maxspeed_mph <= 35 then return 3
        elseif maxspeed_mph and maxspeed_mph > 35 then return 4 end
      end

      -- if we don't have speed or lane info we wind up here
      assert(lanes_each_way == nil or maxspeed_mph == nil, "lanes and maxspeed present but no LTS assigned at way " .. way:id())

      if highway == "unclassified" or highway == "tertiary" or highway == "tertiary_link" or highway == "residential" then
        -- residential was not included in this in the AAA reference implementation, but that leave you with residential streets that are
        -- LTS 3 if they have a bike lane and LTS 1 otherwise. I can see an argument for residential streets with bike lanes being higher
        -- stress than those without, as bike lanes probably proxy for a busier street to begin with.
        return 2
      else
        return 3
      end
  end -- bike lane logic

  if highway == "residential" or highway == "living_street" then
    return 1
  end

  -- #21 - small & slow (under 3 lanes & maxspeed <= 25), LTS 2
  if lanes_total and maxspeed_mph and lanes_total <= 3 and maxspeed_mph <= 25 then
    return 2
  end

  -- #22 -- slow but more than 3 lanes, LTS 3 -- informed by PFB
  if lanes_total and maxspeed_mph and lanes_total > 3 and maxspeed_mph <= 25 then
    return 3
  end

  -- #23 - slow and lanes not specified, LTS 2
  if not lanes_total and maxspeed_mph and maxspeed_mph <= 25 then
    return 2
  end

  -- #24 - highway = tertiary & no assignment yet (built in), LTS 3
  if highway == "tertiary" then
    return 3
  end

  -- #25 - highway = tertiary_link or unclassified & no assignment yet (built in), LTS 2
  if highway == "tertiary_link" or highway == "unclassified" then
    return 2
  end

  -- #26 - highway = primary, trunk, primary_link, trunk_link, & no assignment yet (no separated facilities), LTS 4
  if highway == "primary" or highway == "trunk" or highway == "primary_link" or highway == "trunk_link" then
    return 4
  end

  -- catch-all
  return 4
end

-- A number of functions require information on whether a way is oneway, which is usually created
-- by the oneway way handler. There are two reason why this doesn't work for LTS estimation:
-- 1: one-way streets are not considered one-way for pedestrians, so oneway will always be false
-- 2: In the bike LTS weighting, LTS is calculated before any other data, and we short-circuit and perform
--    walk weighting instead 
function get_oneway_data (way, profile)
  -- code copied and simplified from OSRM WayHandlers.oneway
  data = {
    is_forward_oneway = false,
    is_reverse_oneway = false
  }

  oneway = Tags.get_value_by_prefixed_sequence(way,profile.restrictions,'oneway') or way:get_value_by_key("oneway")
  data.oneway = oneway

  if oneway == "-1" then
    data.is_reverse_oneway = true
  elseif oneway == "yes" or
         oneway == "1" or
         oneway == "true" then
    data.is_forward_oneway = true
  else
    local junction = way:get_value_by_key("junction")
    if data.highway == "motorway" or
       junction == "roundabout" or
       junction == "circular" then
      if oneway ~= "no" then
        -- implied oneway
        data.is_forward_oneway = true
      end
    end
  end

  return data
end

function LTS.get_ltsspeed(way, profile, infer)
  local oneway_data = get_oneway_data(way, profile)

  -- We use the car profile in extracting the maxspeed, as we want the car maxspeed, not the walking maxspeed
  -- copied from WayHandlers.maxspeed, modified to use car_profile
  local keys = Sequence {  'maxspeed:advisory', 'maxspeed', 'source:maxspeed', 'maxspeed:type' }
  local forward, backward = Tags.get_forward_backward_by_set(way,oneway_data,keys)
  forward = WayHandlers.parse_maxspeed(forward, profile.car_profile)
  backward = WayHandlers.parse_maxspeed(backward, profile.car_profile)

  -- find highest maxspeed from forward, backward
  -- TODO figure out how the string.match code based on source in way_handlers.lua works
  local maxspeed = 0
  if forward and forward > maxspeed then
    maxspeed = forward
  end

  if backward and backward > maxspeed then
    maxspeed = backward
  end

  if maxspeed == 0 then
    if infer then
      -- no maxspeed for way, use default speeds from profile, copied from WayHandlers.speed
      local key,value,speed = Tags.get_constant_by_key_value(way,profile.car_profile.speeds)
      if speed then
        maxspeed = speed
      else
        maxspeed = profile.car_profile.default_speed
      end
    else
      return nil
    end
  end

  return maxspeed
end

function LTS.get_lanes(way, profile, infer)
  local lanes_fwd = tonumber(way:get_value_by_key("lanes:forward"))
  local lanes_bwd = tonumber(way:get_value_by_key("lanes:backward"))
  local lanes = tonumber(way:get_value_by_key("lanes"))

  local oneway_data = get_oneway_data(way, profile)

  if lanes_fwd and lanes_bwd then
    return lanes_fwd, lanes_bwd
  elseif data.is_forward_oneway then
    if lanes_fwd then
      return lanes_fwd, 0
    elseif lanes then
      return lanes, 0
    elseif infer then
      return 1, 0
    else
      return nil, nil
    end
  elseif data.is_reverse_oneway then
    if lanes_bwd then
      return 0, lanes_bwd
    elseif lanes then
      return 0, lanes
    elseif infer then
      return 0, 1
    else
      return nil, nil
    end
  else
    -- Not oneway, we don't have lanes_fwd specified
    if lanes then
      return lanes / 2, lanes / 2
    elseif infer then
      return 1, 1
    else
      return nil, nil
    end
  end
end

return LTS