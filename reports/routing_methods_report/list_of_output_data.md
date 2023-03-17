# List of Routing Tools Output Data

This document identifies the agreed-upon outputs from the routing tools.  These outputs will be available for use in visualization and analysis.  

The basic output from the routing analysis is one file for each mode (car, walk, bike, transit), in Geopackage (.gpkg) format.  Each file constitutes a geodatabase that can be opened in standard GIS software.  

For car, walk and bike, there is one record for each trip, identified by the trip_id.  For transit trips, there is one record for each leg.  For example, a bus trip might include a walk access leg, a bus leg, and a walk egress leg.  The trip_id can still be used to aggregate to trips, and a leg_index indicates the sequence of legs.  In all cases, the trip_id is an array of numbers as coded in the processed TBI data.  It is an array, because some legs in the TBI are linked to remove stops at gas stations and transit stops. 

If the trip cannot be routed on a particular mode, the record does not appear.  We expect such cases to be rare in the case of car, walk and bike--occuring for example with a disconnected network--such that subsequent choices about whether a trip is feasible can be decided upon by filtering those records based on the output of the routing. For transit, trips are only routed if both ends are within walking distance of a transit stop.  

In addition to the geometry, each trip record include the following attributes:

### Car 
`car_trips.gpkg` contains a single layer called `car_trips routes` with one record for each route. The attributes on each record include:

- `trip_id` string, identifier for each trip record, formatted as a list.  For car, trips at gas stations are "linked out", so `[12345, 67890]` would indicate that two legs were linked and `[12345]` would indicate a trip with just one leg. 
- `duration_seconds` numeric, duration in seconds
- `distance_meters` numeric, distance in meters
- `weight` numeric, generalized cost as used in the routing

### Walk
`walk_trips.gpkg` contains a single layer called `walk_trips routes` with one record for each route.  The attributes on each record include:

- `trip_id` string, identifier for each trip record, formatted as a list. `[12345]` would indicate a single trip. 
- `duration_seconds` numeric, duration in seconds
- `distance_meters` numeric, distance in meters
- `weight` numeric, generalized cost as used in the routing
- `distance_meters_1` numeric, distance in meters on Pedestrian Traffic Stress (PTS) 1 facilities (best)
- `distance_meters_2` numeric, distance in meters on PTS 2 facilities 
- `distance_meters_3` numeric, distance in meters on PTS 3 facilities 
- `distance_meters_4` numeric, distance in meters on PTS 4 facilities (Worst)
- `distance_meters_slope` numeric, distance in meters on slopes over 10%

### Bike 
`bike_lts.gpkg` contains a layer called `bike_lts routes` with one record for each route.  The attributes on each record include:

- `trip_id` String, identifier for each trip record, formatted as a list. `[12345]` would indicate a single trip. 
- `duration_seconds` numeric, duration in seconds
- `distance_meters` numeric, distance in meters
- `weight` numeric, generalized cost as used in the routing
- `distance_meters_1` numeric, distance in meters on Level of Traffic Stress (LTS) 1 facilities (best)
- `distance_meters_2` numeric, distance in meters on LTS 2 facilities
- `distance_meters_3` numeric, distance in meters on 3 facilities 
- `distance_meters_4` numeric, distance in meters on 4 facilities (worst)
- `elevation_gain_meters` numeric, change in slope calculated consistent with its use in generalized cost

`bike_lts.gpkg` contains a second layer called `bike_lts segments` in which the routes are split into segments any time there is a change in LTS.  This way, we can easily exclude or separately summarize the high LTS facilities.  The attributes on each record include:

- `trip_id` string, identifier for each trip record, formatted as a list. `[12345]` would indicate a single trip. 
- `segment_index` numeric, an index for each segment on a trip, in order.  
- `lts` integer, the level of traffic stress on this segment.
- `distance_meters` numeric, distance in meters

### Transit
`transit_trips.gpkg` contains a single layer called `transit_trips routes` with one record for leg of a transit trip.  For example, a trip that is walk-bus-walk contains three legs and will contain three records in this layer. These attributes are recorded for each leg, and can be aggregated to the trip level.  All transit attributes are as recorded in the GTFS files. The attributes on each record include:


- `trip_id` string, identifier for each trip record, formatted as a list. `[12345, 67890]` would indicate that two legs were linked and `[12345]` would indicate a trip with just one leg. 
- `leg_index` integer, an index for each leg on a trip, in order.  
- `start_time` DateTime, start time.  This is recorded as a DateTime field, and when displayed in QGIS has the format YYYY-MM-DD HH:MM:SS
- `end_time` DateTime, end time. This is recorded as a DateTime field, and when displayed in QGIS has the format YYYY-MM-DD HH:MM:SS
- `origin_stop_id` string, origin stop ID
- `origin_stop_name` string, origin stop name
- `destination_stop_id` string, destination stop ID
- `destination_stop_name` string, destination stop name
- `route_id` string, route ID 
- `route_short_name` string, route short name
- `route_long_name` string, route long name 
- `route_type` integer, route type (usually indicates bus or rail)
- `leg_type` string, leg type (transit, access, egress or transfer)

The start times and end times of car, walk and bike trips will be added when these data are merged with the TBI records. 
 