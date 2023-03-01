local LTS = {}

function LTS.get_ltsspeed(way, profile, data)
  -- We use the car profile in extracting the maxspeed, as we want the car maxspeed, not the walking maxspeed
  -- copied from WayHandlers.maxspeed, modified to use car_profile
  local keys = Sequence {  'maxspeed:advisory', 'maxspeed', 'source:maxspeed', 'maxspeed:type' }
  local forward, backward = Tags.get_forward_backward_by_set(way,data,keys)
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

function LTS.get_lanes(way, data, infer)
  local lanes_fwd = tonumber(way:get_value_by_key("lanes:forward"))
  local lanes_bwd = tonumber(way:get_value_by_key("lanes:backward"))
  local lanes = tonumber(way:get_value_by_key("lanes"))

  if lanes_fwd and lanes_bwd then
    return lanes_fwd, lanes_bwd
  elseif data.oneway then
    if data.is_forward_oneway then
      if lanes_fwd then
        return lanes_fwd, 0
      elseif lanes then
        return lanes, 0
      elseif infer then
        return 1, 0
      else
        return nil, nil
      end
    else
      if lanes_bwd then
        return 0, lanes_bwd
      elseif lanes then
        return 0, lanes
      elseif infer then
        return 0, 1
      else
        return nil, nil
      end
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