# Definition of what is a feasible mode shift

- Trip duration, and the difference in duration between the auto trip and non-driving mode (see Optional Task A for a proposal of a more detailed exploration of time constraints).
- Trip distance
- Season or Weather15
- Whether the trip occurred during daylight hours16
- Number of passengers or children on trip17
- Traveler’s age, disability status, whether or not they drive
- Cargo carrying needs: Though not recorded by the survey, the detailed “trip purpose” variable in the survey includes trips to get groceries or shop for a large item.
- Elevation change (hills on bicycle trips), calculated from the re-routing analysis
- Percent of trip made on higher Level of traffic stress routes (biking, walking), calculated from re-routing analysis
- Other measures of walkability and safety garnered during the re-routing analysis

# More to consider:
- Walk distance > X miles
- Bike distance > X miles
- More than two transfers on transit
- No transit path found
- Transit walking distance for a specific leg > X miles

# More to consider
- Walk: Generalized cost > X
    -    Distance on QOS 1 > X or % of trip on QOS 1 > X
    -    Distance on QOS 2 > X or % of trip on QOS 1 > X
- Bike: Generalized cost > X
    -    Distance on LTS 4 > X or % of trip on LTS 4 > X
    -    Distance on LTS 3 > X or % of trip on LTS 3 > X
- Transit: Time > X

# Conflicts with other trips:
- Work and School are always assumed to be fixed. 
- Dropping off or pickup kids is assumed to be fixed
- On the way to work/school/kid pudo arrival time is held constant, and re-calculate the departure time 
  based on the travel time of the alternate mode. If that departure time is earlier than the arrival time 
  of the previous trip, then we consider it to be an infeasible switc
- On the way home from work/school/kid pudo, departure time is held constatn.  Recalculate the arrival time
  based on teh travel time of the alternative mode.  If that arrival time is later than the departure time
  of the next trip, tehn we consider it to be an infeasible switch. 