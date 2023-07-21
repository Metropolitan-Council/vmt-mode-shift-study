-- Bicycle profile

-- originally 59, from the San Francisco paper, but reduced as that seemed excessive
FLAT_DISTANCE_PER_VERTICAL_METER = 25

-- TODO version incompatibilities with api version 2
api_version = 4

Set = require('lualib/set')
Sequence = require('lualib/sequence')
Handlers = require("lualib/way_handlers")
TrafficSignal = require("lualib/traffic_signal")
find_access_tag = require("lualib/access").find_access_tag
limit = require("lualib/maxspeed").limit
Measure = require("lualib/measure")
walk_profile = require("foot_lts")
car_profile = require("car_traffic")
LTS = require("lts")
elevation = require("elevation")

function setup()
  local default_speed = 12 * 1.609
  local walking_speed = 4

  return {
    properties = {
      u_turn_penalty                = 20,
      traffic_light_penalty         = 2,
      weight_name                   = 'bikelts',
      --weight_name                   = 'duration',
      process_call_tagless_node     = false,
      max_speed_for_map_matching    = 110/3.6, -- kmph -> m/s
      use_turn_restrictions         = false,
      continue_straight_at_waypoint = false,
      mode_change_penalty           = 30,
    },

    -- Penalties for unsignalized intersections of different LTS values, in "weighted seconds"
    unsignalized_intersection_penalties = {
      1,
      20,
      60,
      180 -- heavily avoid unsignalized crossings
    },

    signalized_intersection_penalties = {
      15,
      30,
      60,
      120 -- will generally not be used, only if intersection is all LTS 4
    },

    default_mode              = mode.cycling,
    default_speed             = default_speed,
    walking_speed             = walking_speed,
    oneway_handling           = true,
    turn_penalty              = 6,
    turn_bias                 = 1.4,
    use_public_transport      = false,  -- don't route on railway tracks (?)

    allowed_start_modes = Set {
      mode.cycling,
      mode.pushing_bike
    },

    barrier_blacklist = Set {
      'yes',
      'wall',
      'fence'
    },

    access_tag_whitelist = Set {
      'yes',
      'permissive',
      'designated'
    },

    access_tag_blacklist = Set {
      'no',
      'private',
      'agricultural',
      'forestry',
      'delivery',
      -- When a way is tagged with `use_sidepath` a parallel way suitable for
      -- cyclists is mapped and must be used instead (by law). This tag is
      -- used on ways that normally may be used by cyclists, but not when
      -- a signposted parallel cycleway is available. For purposes of routing
      -- cyclists, this value should be treated as 'no access for bicycles'.
      'use_sidepath'
    },

    restricted_access_tag_list = Set { },

    restricted_highway_whitelist = Set { },

    -- tags disallow access to in combination with highway=service
    service_access_tag_blacklist = Set { },

    construction_whitelist = Set {
      'no',
      'widening',
      'minor',
    },

    access_tags_hierarchy = Sequence {
      'bicycle',
      'vehicle',
      'access'
    },

    restrictions = Set {
      'bicycle'
    },

    cycleway_tags = Set {
      'track',
      'lane',
      'share_busway',
      'sharrow',
      'shared',
      'shared_lane'
    },

    opposite_cycleway_tags = Set {
      'opposite',
      'opposite_lane',
      'opposite_track',
    },

    service_penalties = {
      alley             = 0.0,
    },

    bicycle_speeds = {
      cycleway = default_speed,
      primary = default_speed,
      primary_link = default_speed,
      secondary = default_speed,
      secondary_link = default_speed,
      tertiary = default_speed,
      tertiary_link = default_speed,
      residential = default_speed,
      unclassified = default_speed,
      living_street = default_speed,
      road = default_speed,
      service = default_speed,
      track = default_speed,
      path = default_speed
    },

    pedestrian_speeds = {
      footway = walking_speed,
      pedestrian = walking_speed,
      steps = walking_speed
    },

    railway_speeds = {
      train = 10,
      railway = 10,
      subway = 10,
      light_rail = 10,
      monorail = 10,
      tram = 10
    },

    platform_speeds = {
      platform = walking_speed
    },

    amenity_speeds = {
      parking = default_speed,
      parking_entrance = default_speed
    },

    man_made_speeds = {
      pier = walking_speed
    },

    route_speeds = {
      ferry = 5
    },

    bridge_speeds = {
      movable = default_speed
    },

    surface_speeds = {
      asphalt = default_speed,
      chipseal = default_speed,
      concrete = default_speed,
      concrete_lanes = default_speed,
      wood = default_speed,
      metal = default_speed,
      ["cobblestone:flattened"] = default_speed,
      paving_stones = default_speed,
      compacted = default_speed,
      cobblestone = default_speed,
      unpaved = default_speed,
      fine_gravel = default_speed,
      gravel = default_speed,
      pebblestone = default_speed,
      grass_paver = default_speed,
      ground = default_speed,
      dirt = default_speed,
      earth = default_speed,
      grass = default_speed,
      mud = default_speed,
      sand = default_speed,
      woodchips = default_speed,
      sett = default_speed
    },

    classes = Sequence {
        -- store LTS levels as classes. These will be used in direction output
        -- and also used in calculating turn costs (i.e. crossing costs)
        'ferry', 'tunnel', 'lts1', 'lts2', 'lts3', 'lts4', 'flat'
    },

    -- Which classes should be excludable
    -- This increases memory usage so its disabled by default.
    excludable = Sequence {
--        Set {'ferry'}
    },

    tracktype_speeds = {
    },

    smoothness_speeds = {
    },

    avoid = Set {
      'impassable',
      'construction'
    },

    walk_profile = walk_profile.setup(),
    car_profile = car_profile.setup(),

    -- TODO loading elevation twice in bike and walk profiles
    elevation = load_elevation(),

    -- make sure elevation is calculated in both directions
    force_split_edges = true
  }
end

function process_node(profile, node, result)
  -- parse access and barrier tags
  local highway = node:get_value_by_key("highway")
  local is_crossing = highway and highway == "crossing"

  local access = find_access_tag(node, profile.access_tags_hierarchy)
  if access and access ~= "" then
    -- access restrictions on crossing nodes are not relevant for
    -- the traffic on the road
    if profile.access_tag_blacklist[access] and not is_crossing then
      result.barrier = true
    end
  else
    local barrier = node:get_value_by_key("barrier")
    if barrier and "" ~= barrier then
      if profile.barrier_blacklist[barrier] then
        result.barrier = true
      end
    end
  end

  -- check if node is a traffic light
  result.traffic_lights = TrafficSignal.get_value(node)
end

function handle_bicycle_tags(profile,way,result,data)
    -- initial routability check, filters out buildings, boundaries, etc
  data.route = way:get_value_by_key("route")
  data.man_made = way:get_value_by_key("man_made")
  data.railway = way:get_value_by_key("railway")
  data.amenity = way:get_value_by_key("amenity")
  data.public_transport = way:get_value_by_key("public_transport")
  data.bridge = way:get_value_by_key("bridge")

  if (not data.highway or data.highway == '') and
  (not data.route or data.route == '') and
  (not profile.use_public_transport or not data.railway or data.railway=='') and
  (not data.amenity or data.amenity=='') and
  (not data.man_made or data.man_made=='') and
  (not data.public_transport or data.public_transport=='') --and
  -- don't include bridges not tagged as highways
  --(not data.bridge or data.bridge=='')
  then
    return false
  end

  -- access
  data.access = find_access_tag(way, profile.access_tags_hierarchy)
  if data.access and profile.access_tag_blacklist[data.access] then
    return false
  end

  -- other tags
  data.junction = way:get_value_by_key("junction")
  data.maxspeed = Measure.get_max_speed(way:get_value_by_key ("maxspeed")) or 0
  data.maxspeed_forward = Measure.get_max_speed(way:get_value_by_key("maxspeed:forward")) or 0
  data.maxspeed_backward = Measure.get_max_speed(way:get_value_by_key("maxspeed:backward")) or 0
  data.barrier = way:get_value_by_key("barrier")
  data.oneway = way:get_value_by_key("oneway")
  data.oneway_bicycle = way:get_value_by_key("oneway:bicycle")
  data.cycleway = way:get_value_by_key("cycleway")
  data.cycleway_left = way:get_value_by_key("cycleway:left")
  data.cycleway_right = way:get_value_by_key("cycleway:right")
  data.duration = way:get_value_by_key("duration")
  data.service = way:get_value_by_key("service")
  data.foot = way:get_value_by_key("foot")
  data.foot_forward = way:get_value_by_key("foot:forward")
  data.foot_backward = way:get_value_by_key("foot:backward")
  data.bicycle = way:get_value_by_key("bicycle")

  speed_handler(profile,way,result,data)

  oneway_handler(profile,way,result,data)

  cycleway_handler(profile,way,result,data)

  -- maxspeed
  limit( result, data.maxspeed, data.maxspeed_forward, data.maxspeed_backward )

  -- not routable if no speed assigned
  -- this avoid assertions in debug builds
  if result.forward_speed <= 0 and result.duration <= 0 then
    result.forward_mode = mode.inaccessible
  end
  if result.backward_speed <= 0 and result.duration <= 0 then
    result.backward_mode = mode.inaccessible
  end
end

function speed_handler(profile,way,result,data)

  data.way_type_allows_pushing = false

  -- speed
  local bridge_speed = profile.bridge_speeds[data.bridge]
  if (bridge_speed and bridge_speed > 0) then
    data.highway = data.bridge
    if data.duration and durationIsValid(data.duration) then
      result.duration = math.max( parseDuration(data.duration), 1 )
    end
    result.forward_speed = bridge_speed
    result.backward_speed = bridge_speed
    data.way_type_allows_pushing = true
  elseif profile.route_speeds[data.route] then
    -- ferries (doesn't cover routes tagged using relations)
    result.forward_mode = mode.ferry
    result.backward_mode = mode.ferry
    if data.duration and durationIsValid(data.duration) then
      result.duration = math.max( 1, parseDuration(data.duration) )
    else
       result.forward_speed = profile.route_speeds[data.route]
       result.backward_speed = profile.route_speeds[data.route]
    end
  -- railway platforms (old tagging scheme)
  elseif data.railway and profile.platform_speeds[data.railway] then
    result.forward_speed = profile.platform_speeds[data.railway]
    result.backward_speed = profile.platform_speeds[data.railway]
    data.way_type_allows_pushing = true
  -- public_transport platforms (new tagging platform)
  elseif data.public_transport and profile.platform_speeds[data.public_transport] then
    result.forward_speed = profile.platform_speeds[data.public_transport]
    result.backward_speed = profile.platform_speeds[data.public_transport]
    data.way_type_allows_pushing = true
  -- railways
  elseif profile.use_public_transport and data.railway and profile.railway_speeds[data.railway] and profile.access_tag_whitelist[data.access] then
    result.forward_mode = mode.train
    result.backward_mode = mode.train
    result.forward_speed = profile.railway_speeds[data.railway]
    result.backward_speed = profile.railway_speeds[data.railway]
  elseif data.amenity and profile.amenity_speeds[data.amenity] then
    -- parking areas
    result.forward_speed = profile.amenity_speeds[data.amenity]
    result.backward_speed = profile.amenity_speeds[data.amenity]
    data.way_type_allows_pushing = true
  elseif profile.bicycle_speeds[data.highway] then
    -- regular ways
    result.forward_speed = profile.bicycle_speeds[data.highway]
    result.backward_speed = profile.bicycle_speeds[data.highway]
    data.way_type_allows_pushing = true
  elseif data.access and profile.access_tag_whitelist[data.access]  then
    -- unknown way, but valid access tag
    result.forward_speed = profile.default_speed
    result.backward_speed = profile.default_speed
    data.way_type_allows_pushing = true
  end
end

function oneway_handler(profile,way,result,data)
  -- oneway
  data.implied_oneway = data.junction == "roundabout" or data.junction == "circular" or data.highway == "motorway"
  data.reverse = false

  if data.oneway_bicycle == "yes" or data.oneway_bicycle == "1" or data.oneway_bicycle == "true" then
    result.backward_mode = mode.inaccessible
  elseif data.oneway_bicycle == "no" or data.oneway_bicycle == "0" or data.oneway_bicycle == "false" then
   -- prevent other cases
  elseif data.oneway_bicycle == "-1" then
    result.forward_mode = mode.inaccessible
    data.reverse = true
  elseif data.oneway == "yes" or data.oneway == "1" or data.oneway == "true" then
    result.backward_mode = mode.inaccessible
  elseif data.oneway == "no" or data.oneway == "0" or data.oneway == "false" then
    -- prevent other cases
  elseif data.oneway == "-1" then
    result.forward_mode = mode.inaccessible
    data.reverse = true
  elseif data.implied_oneway then
    result.backward_mode = mode.inaccessible
  end
end

function cycleway_handler(profile,way,result,data)
  -- cycleway
  data.has_cycleway_forward = false
  data.has_cycleway_backward = false
  data.is_twoway = result.forward_mode ~= mode.inaccessible and result.backward_mode ~= mode.inaccessible and not data.implied_oneway

  -- cycleways on normal roads
  if data.is_twoway then
    if data.cycleway and profile.cycleway_tags[data.cycleway] then
      data.has_cycleway_backward = true
      data.has_cycleway_forward = true
    end
    if (data.cycleway_right and profile.cycleway_tags[data.cycleway_right]) or (data.cycleway_left and profile.opposite_cycleway_tags[data.cycleway_left]) then
      data.has_cycleway_forward = true
    end
    if (data.cycleway_left and profile.cycleway_tags[data.cycleway_left]) or (data.cycleway_right and profile.opposite_cycleway_tags[data.cycleway_right]) then
      data.has_cycleway_backward = true
    end
  else
    local has_twoway_cycleway = (data.cycleway and profile.opposite_cycleway_tags[data.cycleway]) or (data.cycleway_right and profile.opposite_cycleway_tags[data.cycleway_right]) or (data.cycleway_left and profile.opposite_cycleway_tags[data.cycleway_left])
    local has_opposite_cycleway = (data.cycleway_left and profile.opposite_cycleway_tags[data.cycleway_left]) or (data.cycleway_right and profile.opposite_cycleway_tags[data.cycleway_right])
    local has_oneway_cycleway = (data.cycleway and profile.cycleway_tags[data.cycleway]) or (data.cycleway_right and profile.cycleway_tags[data.cycleway_right]) or (data.cycleway_left and profile.cycleway_tags[data.cycleway_left])

    -- set cycleway even though it is an one-way if opposite is tagged
    if has_twoway_cycleway then
      data.has_cycleway_backward = true
      data.has_cycleway_forward = true
    elseif has_opposite_cycleway then
      if not data.reverse then
        data.has_cycleway_backward = true
      else
        data.has_cycleway_forward = true
      end
    elseif has_oneway_cycleway then
      if not data.reverse then
        data.has_cycleway_forward = true
      else
        data.has_cycleway_backward = true
      end

    end
  end

  if data.has_cycleway_backward then
    result.backward_mode = mode.cycling
    result.backward_speed = profile.bicycle_speeds["cycleway"]
  end

  if data.has_cycleway_forward then
    result.forward_mode = mode.cycling
    result.forward_speed = profile.bicycle_speeds["cycleway"]
  end
end

function bike_push_handler(profile,way,result,data)
  -- pushing bikes - if no other mode found
  if result.forward_mode == mode.inaccessible or result.backward_mode == mode.inaccessible or
    result.forward_speed == -1 or result.backward_speed == -1 then
    if data.foot ~= 'no' then
      local push_forward_speed = nil
      local push_backward_speed = nil

      if profile.pedestrian_speeds[data.highway] then
        push_forward_speed = profile.pedestrian_speeds[data.highway]
        push_backward_speed = profile.pedestrian_speeds[data.highway]
      elseif data.man_made and profile.man_made_speeds[data.man_made] then
        push_forward_speed = profile.man_made_speeds[data.man_made]
        push_backward_speed = profile.man_made_speeds[data.man_made]
      else
        if data.foot == 'yes' then
          push_forward_speed = profile.walking_speed
          if not data.implied_oneway then
            push_backward_speed = profile.walking_speed
          end
        elseif data.foot_forward == 'yes' then
          push_forward_speed = profile.walking_speed
        elseif data.foot_backward == 'yes' then
          push_backward_speed = profile.walking_speed
        elseif data.way_type_allows_pushing then
          push_forward_speed = profile.walking_speed
          if not data.implied_oneway then
            push_backward_speed = profile.walking_speed
          end
        end
      end

      if push_forward_speed and (result.forward_mode == mode.inaccessible or result.forward_speed == -1) then
        result.forward_mode = mode.pushing_bike
        result.forward_speed = push_forward_speed
      end
      if push_backward_speed and (result.backward_mode == mode.inaccessible or result.backward_speed == -1)then
        result.backward_mode = mode.pushing_bike
        result.backward_speed = push_backward_speed
      end

    end

  end

  -- dismount
  if data.bicycle == "dismount" then
    result.forward_mode = mode.pushing_bike
    result.backward_mode = mode.pushing_bike
    result.forward_speed = profile.walking_speed
    result.backward_speed = profile.walking_speed
  end
end

-- add a weight of 1.1x for LTS 2
function lts_weighter(profile, way, result, data)
  if data.lts == 2 then
    -- 10% penalty for LTS 2 vs 1
    if result.forward_speed > 0 then
      result.forward_speed = result.forward_speed / 1.1
      result.forward_rate = result.forward_speed / 3.6 / 1.1
    else
      result.forward_rate = -1
    end

    if result.backward_speed > 0 then
      result.backward_speed = result.backward_speed / 1.1
      result.backward_rate = result.backward_speed / 3.6 / 1.1
    else
      result.backward_rate = -1
    end
  else
    --  assert(data.lts == 1, "LTS not 1 when it should be at way" .. way:id())
    
    if result.forward_speed > 0 then
      result.forward_rate = result.forward_speed / 3.6
    else
      result.forward_rate = -1
    end

    if result.backward_speed > 0 then
      result.backward_rate = result.backward_speed / 3.6
    else
      result.backward_rate = -1
    end
  end

  -- use highway classification to store LTS so it's available in turns
  -- This will mess up guidance/direction generation, but should not affect routes
  result.road_classification.road_priority_class = data.lts

  --assert(result.forward_speed > 0 and result.backward_speed > 0 and result.forward_rate > 0 and result.backward_rate > 0, "speeds/rates not positive at way " .. way:id())
end

function process_way(profile, way, result)
  -- the initial filtering of ways based on presence of tags
  -- affects processing times significantly, because all ways
  -- have to be checked.
  -- to increase performance, prefetching and initial tag check
  -- is done directly instead of via a handler.

  -- We first check LTS. If it's over 2, we short-circuit and hand off to the
  -- walk profile as we assume people walk their bikes in these locations
  local lts = LTS.lts_for_way(profile, way)
  -- special LTS 5 is LTS 4 but does not bleed into intersections
  assert(lts > 0 and lts <= 5, "Found unexpected LTS " .. lts .. " at way " .. way:id())

  if lts == 1 then
     result.forward_classes["lts1"] = true
     result.backward_classes["lts1"] = true
  elseif lts == 2 then
     result.forward_classes["lts2"] = true
     result.backward_classes["lts2"] = true
  elseif lts == 3 then
     result.forward_classes["lts3"] = true
     result.backward_classes["lts3"] = true
  elseif lts == 4 or lts == 5 then -- LTS 5 is like LTS 4 but does not bleed through intersections
     result.forward_classes["lts4"] = true
     result.backward_classes["lts4"] = true
  end

  assert(lts >= 1 and lts <= 5, "Unexpected LTS " .. lts .. " at way " .. way:id())

  if lts <= 2 then
    -- process as bike segment

    -- in general we should try to abort as soon as
    -- possible if the way is not routable, to avoid doing
    -- unnecessary work. this implies we should check things that
    -- commonly forbids access early, and handle edge cases later.

    -- data table for storing intermediate values during processing

    local data = {
      -- prefetch tags
      highway = way:get_value_by_key('highway'),

      route = nil,
      man_made = nil,
      railway = nil,
      amenity = nil,
      public_transport = nil,
      bridge = nil,

      access = nil,

      junction = nil,
      maxspeed = nil,
      maxspeed_forward = nil,
      maxspeed_backward = nil,
      barrier = nil,
      oneway = nil,
      oneway_bicycle = nil,
      cycleway = nil,
      cycleway_left = nil,
      cycleway_right = nil,
      duration = nil,
      service = nil,
      foot = nil,
      foot_forward = nil,
      foot_backward = nil,
      bicycle = nil,

      way_type_allows_pushing = false,
      has_cycleway_forward = false,
      has_cycleway_backward = false,
      is_twoway = true,
      reverse = false,
      implied_oneway = false,

      lts = lts
    }

    local handlers = Sequence {
      -- set the default mode for this profile. if can be changed later
      -- in case it turns we're e.g. on a ferry
      WayHandlers.default_mode,

      -- check various tags that could indicate that the way is not
      -- routable. this includes things like status=impassable,
      -- toll=yes and oneway=reversible
      WayHandlers.blocked_ways,

      -- our main handler
      handle_bicycle_tags,

      -- compute speed taking into account way type, maxspeed tags, etc.
      WayHandlers.surface,

      -- handle turn lanes and road classification, used for guidance
      -- don't overwrite LTS values
      --WayHandlers.classification,

      -- -- handle allowed start/end modes
      -- startpoint now idnicates bridge/tunnel
      -- WayHandlers.startpoint,

      -- handle roundabouts
      WayHandlers.roundabouts,

      -- set name, ref and pronunciation
      WayHandlers.names,

      -- set classes
      WayHandlers.classes,

      -- set weight properties of the way
      WayHandlers.weights,

      lts_weighter,

      mark_bridges_and_tunnels
    }

    WayHandlers.run(profile, way, result, data, handlers)
  end

  -- handle walking bikes by calling out to the walk profile. We walk bikes if LTS > 2 or biking is not allowed.
  -- TODO audit the walk profile to make sure nothing in there is affected by the bike profile being run first
  -- in places where biking is not allowed.
  if lts > 2 or result.forward_mode == mode.inaccessible or result.backward_mode == mode.inaccessible or
    result.forward_speed == -1 or result.backward_speed == -1 or data.bicycle == "dismount" then
    -- process as a walk-bike segment
    walk_profile.process_way(profile.walk_profile, way, result)

    -- and apply a 25% speed and weight penalty to account for walking the bike
    if result.forward_speed > 0 then
      assert(result.forward_rate > 0)
      -- TODO no penalty
      result.forward_speed = result.forward_speed
      result.forward_rate = result.forward_rate
      result.forward_mode = mode.pushing_bike
    end

    if result.backward_speed > 0 then
      assert(result.backward_rate > 0)
      result.backward_speed = result.backward_speed
      result.backward_rate = result.backward_rate
      result.backward_mode = mode.pushing_bike
    end
  end
  
  -- Store LTS as road priority class so we can access it in process_turn
  -- This will reduce the quality of the narrative directions, but should not affect routing.
  result.road_classification.road_priority_class = lts
end

function process_turn(profile, turn)
  -- TODO: on an LTS 3-4 turn, should we use the pedestrian turn weighting?

  turn.duration = 0
  turn.weight = 0

  if turn.has_traffic_light then
    -- minimum of all LTS at intersection
    lts = math.min(turn.source_priority_class, turn.target_priority_class)

    for i,road in ipairs(turn.roads_on_the_right) do
      if road.priority_class < lts then lts = road.priority_class end
    end

    for i,road in ipairs(turn.roads_on_the_left) do
      if road.priority_class < lts then lts = road.priority_class end
    end

    -- LTS 5 is used for service roads, a special LTS 4 derivative that does not bleed
    -- onto crossing roads.
    -- Will only happen at intersections between all service roads, as otherwise there would be a lower min LTS
    if lts == 5 then lts = 4 end

    local weight = profile.signalized_intersection_penalties[lts]

    if weight == nil then
      print("WARN: weight was nil for lts " .. lts)
      weight = 1
    end

    turn.duration = weight
    turn.weight = weight

    assert(turn.duration > 0 and turn.weight > 0, "Signalized LTS " .. lts .. " turn does not have duration/weight")

  else
    -- We want to ignore LTS 5 (service) 
    lts = 1
    if turn.source_priority_class > lts and turn.source_priority_class ~= 5 then
      lts = turn.source_priority_class
    end

    if turn.target_priority_class > lts and turn.target_priority_class ~= 5 then
      lts = turn.target_priority_class
    end


    -- maximum of all LTS at intersection
    -- priority class 5 is a special class that's treated like class 4 for node weights, but does
    -- not bleed over to streets. See the Beaudry Meadows Park test for an example of why this is
    -- needed
    for i,road in ipairs(turn.roads_on_the_right) do
      if road.priority_class > lts and road.priority_class ~= 5 then lts = road.priority_class end
    end

    for i,road in ipairs(turn.roads_on_the_left) do
      if road.priority_class > lts and road.priority_class ~= 5 then lts = road.priority_class end
    end

    local weight = profile.unsignalized_intersection_penalties[lts]
    if weight == nil then
      print("WARN: weight was nil for lts " .. lts)
      weight = 1
    end
    turn.duration = weight
    turn.weight = weight
    assert(turn.duration > 0 and turn.weight > 0, "Unsignalized LTS " .. lts .. " turn does not have duration/weight")
  end

  assert(turn.duration > 0 and turn.weight > 0, "Turn does not have duration/weight")
end

function process_segment(profile, segment)
  -- ignore if it's not a startpoint (i.e. it's a bridge or tunnel)
  if segment.flags.startpoint then
    local elevation_gain_mm = get_elevation_gain_mm(profile.elevation, segment.source, segment.target, segment.distance)
    --print("Elevation gain " .. elevation_gain_mm .. "mm")
    --print("Weight was " .. segment.weight)
    -- calculate the weight factor. Each meter of elevation gain is equivalent to an additional 59 meters flat.
    local weight_per_meter = segment.weight / segment.distance
    segment.weight = segment.weight + weight_per_meter * FLAT_DISTANCE_PER_VERTICAL_METER * math.max(0, elevation_gain_mm) / 1000
    --print("Weight is " .. segment.weight)
  else
    print("Skipping elevation on non-startpoint (bridge/tunnel)")
  end
end

return {
  setup = setup,
  process_way = process_way,
  process_node = process_node,
  process_turn = process_turn,
  process_segment = process_segment
}
