-- Foot profile

api_version = 2

Set = require('lualib/set')
Sequence = require('lualib/sequence')
Handlers = require("lualib/way_handlers")
Tags = require("lualib/tags")
find_access_tag = require("lualib/access").find_access_tag
drive_profile = require("car_traffic")
LTS = require("lts")

local miles_to_kilometers = 1.609

local FunctionalClass = {
  freeway = 1,
  major = 2,
  minor = 3,
  local_road = 4,
  pedestrian = 5
}

function setup()
  -- 4.86 km/h = 1.35 m/s. Units not documented in ORSM but appear to be km/h
  local walking_speed = 4.86
  return {
    properties = {
      weight_name                   = 'weight',
      max_speed_for_map_matching    = 40/3.6, -- kmph -> m/s
      call_tagless_node_function    = false,
      traffic_light_penalty         = 2,
      u_turn_penalty                = 2,
      continue_straight_at_waypoint = false,
      use_turn_restrictions         = false,
    },

    -- map OSM highway tags 
    functional_classes = {
      highway = {
        motorway = FunctionalClass.freeway,
        motorway_link = FunctionalClass.freeway,
        trunk = FunctionalClass.major,
        primary = FunctionalClass.major,
        trunk_link = FunctionalClass.major,
        primary_link = FunctionalClass.major,
        secondary = FunctionalClass.minor,
        secondary_link = FunctionalClass.minor,
        tertiary = FunctionalClass.minor,
        tertiary_link = FunctionalClass.minor,
        unclassified = FunctionalClass.minor,
        unclassified_link = FunctionalClass.minor,
        -- not specifying local roads here, this is the default
        footway = FunctionalClass.pedestrian,
        cycleway = FunctionalClass.pedestrian,
        path = FunctionalClass.pedestrian
      }
    },

    -- Weight multipliers for different qualities, from Hardy et al
    quality_multipliers = {
      high = 1.0,
      medium = 3.0 / 2.7,
      low = 3.0 / 2.4,
      available = 3.0 / 1.5
    },

    default_mode            = mode.walking,
    default_speed           = walking_speed,
    oneway_handling         = 'specific',     -- respect 'oneway:foot' but not 'oneway'

    barrier_blacklist = Set {
      'yes',
      'wall',
      'fence'
    },

    access_tag_whitelist = Set {
      'yes',
      'foot',
      'permissive',
      'designated'
    },

    access_tag_blacklist = Set {
      'no',
      'agricultural',
      'forestry',
      'private',
      'delivery',
    },

    restricted_access_tag_list = Set { },

    restricted_highway_whitelist = Set { },

    construction_whitelist = Set {},

    access_tags_hierarchy = Sequence {
      'foot',
      'access'
    },

    -- tags disallow access to in combination with highway=service
    service_access_tag_blacklist = Set { },

    restrictions = Sequence {
      'foot'
    },

    -- list of suffixes to suppress in name change instructions
    suffix_list = Set {
      'N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'North', 'South', 'West', 'East'
    },

    avoid = Set {
      'impassable'
    },

    speeds = Sequence {
      highway = {
        primary         = walking_speed,
        primary_link    = walking_speed,
        secondary       = walking_speed,
        secondary_link  = walking_speed,
        tertiary        = walking_speed,
        tertiary_link   = walking_speed,
        unclassified    = walking_speed,
        residential     = walking_speed,
        road            = walking_speed,
        living_street   = walking_speed,
        service         = walking_speed,
        track           = walking_speed,
        path            = walking_speed,
        steps           = walking_speed,
        pedestrian      = walking_speed,
        footway         = walking_speed,
        pier            = walking_speed,
      },

      railway = {
        platform        = walking_speed
      },

      amenity = {
        parking         = walking_speed,
        parking_entrance= walking_speed
      },

      man_made = {
        pier            = walking_speed
      },

      leisure = {
        track           = walking_speed
      }
    },

    route_speeds = {
      ferry = 5
    },

    bridge_speeds = {
    },

    surface_speeds = {
      fine_gravel =   walking_speed*0.75,
      gravel =        walking_speed*0.75,
      pebblestone =   walking_speed*0.75,
      mud =           walking_speed*0.5,
      sand =          walking_speed*0.5
    },

    tracktype_speeds = {
    },

    smoothness_speeds = {
    },

    -- the car profile is used in determining maxspeeds for perceived safety
    car_profile = drive_profile.setup()
  }
end

function process_node(profile, node, result)
  -- parse access and barrier tags
  local access = find_access_tag(node, profile.access_tags_hierarchy)
  if access then
    if profile.access_tag_blacklist[access] then
      result.barrier = true
    end
  else
    local barrier = node:get_value_by_key("barrier")
    if barrier then
      --  make an exception for rising bollard barriers
      local bollard = node:get_value_by_key("bollard")
      local rising_bollard = bollard and "rising" == bollard

      if profile.barrier_blacklist[barrier] and not rising_bollard then
        result.barrier = true
      end
    end
  end

  -- check if node is a traffic light
  local tag = node:get_value_by_key("highway")
  if "traffic_signals" == tag then
    -- Direction should only apply to vehicles
    result.traffic_lights = true
  end
end

-- Handle the walking quality, using the methodology described in Hardy et al. (2019)
-- "Prohibited" is not handled here, only available, low, medium, and high. We leave
-- Prohibited to be handled by the existing OSRM processing code.
function get_walking_quality_multiplier(profile, way, data)
  -- first, extract some information about the way
  local maxspeed = LTS.get_ltsspeed(way, profile, data)

  -- handle lanes
  -- TODO lanes on dual carriageways. On a dual carriageway, lanes will be the one-direction lanes
  -- while on a single carriageway lanes are supposed to be the sum of lanes in both directions, though
  -- the OSM wiki suggests that this is often mapped incorrectly as per-direction lanes.
  local lanes_fwd, lanes_bwd = LTS.get_lanes(way, data, true)
  local lanes = lanes_fwd + lanes_bwd

  -- check for sidewalk _tagged on way_
  -- Sidewalks mapped as separate ways are treated as low-stress footpaths
  local sidewalk_tag = way:get_value_by_key("sidewalk")
  local sidewalk_both_tag = way:get_value_by_key("sidewalk:both")
  local sidewalk_left_tag = way:get_value_by_key("sidewalk:left")
  local sidewalk_right_tag = way:get_value_by_key("sidewalk:right")

  function tag_indicates_sidewalk (tag)
    return tag == "both" or tag == "left" or tag == "right" or tag == "yes"
  end

  has_sidewalk = tag_indicates_sidewalk(sidewalk_tag) or tag_indicates_sidewalk(sidewalk_both_tag) or
    tag_indicates_sidewalk(sidewalk_left_tag) or tag_indicates_sidewalk(sidewalk_right_tag)

  -- compute road class
  local rkey, rval, rclass = Tags.get_constant_by_key_value(way, profile.functional_classes)
  if not rclass then
    -- anything not specified considered a local road
    rclass = FunctionalClass.local_road
  end

  -- convert max speed to MPH to match Hardy et al
  maxspeed_mph = maxspeed / miles_to_kilometers

  -- now, compute the multiplier
  if rclass == FunctionalClass.pedestrian then
    -- pedestrian-only roads always "high" quality
    return profile.quality_multipliers.high

  elseif has_sidewalk then
    
    if lanes >= 6 then
      if maxspeed_mph >= 55 then
        -- doesn't matter what functional class is
        return profile.quality_multipliers.available
      else
        return profile.quality_multipliers.low
      end
    
    elseif lanes >= 4 then
      if maxspeed_mph >= 55 then
        return profile.quality_multipliers.available
      elseif maxspeed_mph >= 41 then
        return profile.quality_multipliers.low
      elseif maxspeed_mph >= 31 then
        if rclass == FunctionalClass.freeway or rclass == FunctionalClass.major then
          return profile.quality_multipliers.low
        else
          return profile.quality_multipliers.medium
        end
      else
        if rclass == FunctionalClass.freeway or rclass == FunctionalClass.major then
          return profile.quality_multipliers.low
        elseif rclass == FunctionalClass.minor then
          return profile.quality_multipliers.medium
        else
          assert(rclass == FunctionalClass.local_road, "expected only a local road but found road class " .. rclass .. " at way " .. way:id())
          return profile.quality_multipliers.high
        end
      end

    else
      -- less than 4 lanes, almost identical to 4 lanes except major arterial less than 30 mph
      if maxspeed_mph >= 55 then
        return profile.quality_multipliers.available
      elseif maxspeed_mph >= 41 then
        return profile.quality_multipliers.low
      elseif maxspeed_mph >= 31 then
        if rclass == FunctionalClass.freeway or rclass == FunctionalClass.major then
          return profile.quality_multipliers.low
        else
          return profile.quality_multipliers.medium
        end
      else
        if rclass == FunctionalClass.freeway then
          return profile.quality_multipliers.low
        elseif rclass == FunctionalClass.minor or rclass == FunctionalClass.major then
          return profile.quality_multipliers.medium
        else
          assert(rclass == FunctionalClass.local_road, "expected only a local road but found road class " .. rclass .. " at way " .. way:id())
          return profile.quality_multipliers.high
        end
      end
    end
  
  else
    -- ways with no sidewalk, only considered medium if lanes < 4 and and speed < 31 mph and not freeway
    if lanes < 4 and maxspeed_mph < 31 and rclass ~= FunctionalClass.freeway then
      return profile.quality_multipliers.medium
    else
      return profile.quality_multipliers.available
    end
  end

  -- we should have returned by now. If not, there was an error!
  assert(false, "quality multiplier not found (logic error)")
end

-- main entry point for processsing a way
function process_way(profile, way, result)
  -- the intial filtering of ways based on presence of tags
  -- affects processing times significantly, because all ways
  -- have to be checked.
  -- to increase performance, prefetching and intial tag check
  -- is done in directly instead of via a handler.

  -- in general we should  try to abort as soon as
  -- possible if the way is not routable, to avoid doing
  -- unnecessary work. this implies we should check things that
  -- commonly forbids access early, and handle edge cases later.

  -- data table for storing intermediate values during processing
  local data = {
    -- prefetch tags
    highway = way:get_value_by_key('highway'),
    bridge = way:get_value_by_key('bridge'),
    route = way:get_value_by_key('route'),
    leisure = way:get_value_by_key('leisure'),
    man_made = way:get_value_by_key('man_made'),
    railway = way:get_value_by_key('railway'),
    platform = way:get_value_by_key('platform'),
    amenity = way:get_value_by_key('amenity'),
    public_transport = way:get_value_by_key('public_transport')
  }

  -- perform an quick initial check and abort if the way is
  -- obviously not routable. here we require at least one
  -- of the prefetched tags to be present, ie. the data table
  -- cannot be empty
  if next(data) == nil then     -- is the data table empty?
    return
  end

  local handlers = Sequence {
    -- set the default mode for this profile. if can be changed later
    -- in case it turns we're e.g. on a ferry
    WayHandlers.default_mode,

    -- check various tags that could indicate that the way is not
    -- routable. this includes things like status=impassable,
    -- toll=yes and oneway=reversible
    WayHandlers.blocked_ways,

    -- determine access status by checking our hierarchy of
    -- access tags, e.g: motorcar, motor_vehicle, vehicle
    WayHandlers.access,

    -- check whether forward/backward directons are routable
    WayHandlers.oneway,

    -- check whether forward/backward directons are routable
    WayHandlers.destinations,

    -- check whether we're using a special transport mode
    WayHandlers.ferries,
    WayHandlers.movables,

    -- compute speed taking into account way type, maxspeed tags, etc.
    WayHandlers.speed,
    WayHandlers.surface,

    -- handle turn lanes and road classification, used for guidance
    WayHandlers.classification,

    -- handle various other flags
    WayHandlers.roundabouts,
    WayHandlers.startpoint,

    -- set name, ref and pronunciation
    WayHandlers.names,

    -- set weight properties of the way
    WayHandlers.weights
  }

  WayHandlers.run(profile, way, result, data, handlers)

  -- apply multiplier
  local multiplier = get_walking_quality_multiplier(profile, way, data)

  
  -- divide by the multiplier... because these are rates (think km/h but instead generalized cost / h)
  -- we divide by the multiplier - we want to reduce the rate on low-quality facilities.
  -- Note that we are setting based on speed - rate is not set in default OSRM foot routing profile.
  result.forward_rate = result.forward_speed / multiplier
  result.backward_rate = result.backward_speed / multiplier
end

function process_turn (profile, turn)
  turn.duration = 0.

  -- TODO For some unknown reason, direction_modifier is undefined when this profile is used, but
  -- is defined when the almost-identical foot.lua from which this profile is derived is used. It's defined
  -- in scripting_environment_lua.cpp in OSRM, not a clue why it suddenly disappears. Just don't use it for
  -- the time being
  -- if turn.direction_modifier == direction_modifier.u_turn then
  --    turn.duration = turn.duration + profile.properties.u_turn_penalty
  -- end

  if turn.has_traffic_light then
     turn.duration = profile.properties.traffic_light_penalty
  end
  if profile.properties.weight_name == 'routability' then
      -- penalize turns from non-local access only segments onto local access only tags
      if not turn.source_restricted and turn.target_restricted then
          turn.weight = turn.weight + 3000
      end
  end
end

return {
  setup = setup,
  process_way =  process_way,
  process_node = process_node,
  process_turn = process_turn
}
