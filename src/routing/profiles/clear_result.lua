-- clear a result object
-- this is used in bike routing, when it is determined after bike routing that this should actually be processed as
-- a walk-bike segment. The walk profile is affected (at least) by speeds already being set, so this clears that out.

function clear_result(result)
    result.forward_speed = -1
    result.backward_speed = -1
    result.forward_rate = -1
    result.backward_rate = -1
    result.duration = -1
    result.weight = -1
    result.forward_mode = mode.inaccessible
    result.backward_mode = mode.inaccessible
    result.roundabout = false
    result.circular = false
    result.is_startpoint = true
    result.forward_restricted = false
    result.backward_restricted = false
    result.is_left_hand_driving = false
    result.highway_turn_classification = 0
    result.access_turn_classification = 0
    -- Note: this does not reset road classification, classes, or any of the string values. I don't
    -- believe those are used in the profile.
end