# List of Routing Tools Output Data

This document identifies the agreed-upon outputs from the routing tools.  These outputs will be available for use in visualization and analysis.  

The basic output from the routing analysis is one file for each mode (car, walk, bike, transit), in Geopackage (.gpkg) format.  Each file constitutes a geodatabase that can be opened in standard GIS software.  

For car, walk and bike, there is one record for each trip, identified by the trip_id.  For transit trips, there is one record for each leg.  For example, a bus trip might include a walk access leg, a bus leg, and a walk egress leg.  The trip_id can still be used to aggregate to trips, and a leg_index indicates the sequence of legs.  In all cases, the trip_id is an array of numbers as coded in the processed TBI data.  It is an array, because some legs in the TBI are linked to remove stops at gas stations and transit stops. 

If the trip cannot be routed on a particular mode, the record does not appear.  We expect such cases to be rare in the case of car, walk and bike--occuring for example with a disconnected network--such that subsequent choices about whether a trip is feasible can be decided upon by filtering those records based on the output of the routing. For transit, trips are only routed if both ends are within walking distance of a transit stop.  

In addition to the geometry, each trip record include the following attributes:

### Car
- Duration in seconds
- Distance in meters
- Generalized cost (as used in the routing)

### Walk
- Duration in seconds
- Distance in meters
- Generalized cost (as used in the routing)
- Distance in meters on pedestrian Quality of Service (QOS) 1 facilities (Available)
- Distance in meters on pedestrian QOS 2 facilities (Low QOS)
- Distance in meters on pedestrian QOS 3 facilities (Medium QOS)
- Distance in meters on pedestrian QOS 4 facilities (High QOS)
- Distance in meters on slopes over 10%

### Bike 
- Duration in seconds
- Distance in meters
- Generalized cost (as used in the routing)
- Distance in meters on Level of Traffic Stress (LTS) 1 facilities (best)
- Distance in meters on LTS 2 facilities 
- Distance in meters on LTS 3 facilities 
- Distance in meters on LTS 4 facilities (worst)
- Distance in meters on pedestrian QOS 3 facilities (Medium QOS)
- Distance in meters on pedestrian QOS 4 facilities (High QOS)
- Change in slope calculated consistent with its use in generalized cost

### Transit
These attributes are recorded for each leg, and can be aggregated to the trip level.  All transit attributes are as recorded in the GTFS files. 

- Start time
- End time
- Duration in seconds
- Origin stop ID
- Origin stop name
- Destination stop ID
- Destination stop name
- Route ID 
- Route short name
- Route long name 
- Route type
- Leg type (transit, access, egress or transfer)

The start times and end times of car, walk and bike trips will be added when these data are merged with the TBI records. 
 