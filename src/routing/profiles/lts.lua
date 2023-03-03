Tags = require("lualib/tags")

local LTS = {}

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

function LTS.get_ltsspeed(way, profile)
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
    -- no maxspeed for way, use default speeds from profile, copied from WayHandlers.speed
    local key,value,speed = Tags.get_constant_by_key_value(way,profile.car_profile.speeds)
    if speed then
      maxspeed = speed
    else
      maxspeed = profile.car_profile.default_speed
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