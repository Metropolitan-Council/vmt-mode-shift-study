# Routing result changelog

<!-- copied from the routing engine output files in `Data_Processed` -->

This file details what the current latest files from the routing engine are, any known issues, and as new versions are added will detail the changes made in each.

## Current files

All files are in the `Data_Processed/geodata` folder.

| Mode                              | File                                        |
|:----------------------------------|:--------------------------------------------|
| Walk                              | `walk-trips-1d39c.parquet`                  |
| Walk scenario                     | `walk-scenario-a37e1.parquet`               |
| Bike                              | `bike-lts-37721.parquet`                  |
| Bike scenario                     | `bike-all-lts1-37721.parquet`               |
| E-bike scenario                   | `bike-ebike-8a1a0-1.parquet`                 |
| Car (one file per time period)    | `car-congestion-1d39c/*`                    |
| Transit                           | `transit-trips-45d51.parquet`               |
| Transit, no transfers             | (superseded)          |
| Transit, scenario                 | `transit-scenario-0277d.parquet`            |
| Transit, no transfers, scenario   | (superseded) |

There are also file `transit-0.9mi-{baseline,scenario}-f416301.parquet` that are versions of the baseline and scenario files with a 0.9 mile walk limit, to see how this affects the results. If we use these we lose the ability to control that threshold at runtime, so they are currently considered experimental so we can see how much that affects the results.

## Changelogs

### Walk

#### `walk-trips-1d39c.parquet`

- Elevation now accounted for

### Walk scenario

#### `walk-scenario-a37e1.parquet`

- Initial walk scenario

##### Known issues

- There are some trips that are longer distance-wise in the scenario than the original.  I am aware of two causes for this. The main reason for this is that these trips were previously using gravel roads/trails, which have low pedestrian stress, but are penalized by OSRM (at least using the current settings – we could turn that off if desired). In the scenario, the router finds a longer but faster path on paved roads that were previously penalized due to pedestrian stress.

The other way is through elevation, and is a similar argument; there is a path that is penalized for being steep, and OSRM finds an alternative flatter but longer path along roads that are high stress in the baseline. This is less common (at least for creating significant differences), because the slope penalty is pretty mild for walking. This also leads to some trips that are longer in duration in the scenario, because we only penalize weight not travel time for slope. So a flatter path might have a lower weight but a longer duration.

### Bike

#### `bike-lts-37721.parquet`

- This fixes confusion between the scenario and baseline results in the previous file

#### `bike-trips-fe43e.parquet`

**Issue: In this file, there is zero distance on LTS 2, 3 and 4. Revert to bike-trips-1d39c.parquet until this is resolved. gde 9.13.2023** 

- This fixes an issue where low-LTS one-way streets were treated as bikeable in both directions
- Elevation gain is now calculated over each 10m chunk of a segment, rather than as the delta from start to end. Many segments (between two consective OSM nodes) are less than 10m anyhow.

#### `bike-trips-1d39c.parquet`

- Elevation is now accounted for.
- There is no longer an additional weight/time penalty beyond the walking time for walking bikes, and when walking a bike the intersection penalties now match the walking profile, rather than the biking profile. This change had a pretty significant impact, the median routed bike trip is now only 4% longer than the corresponding observed bike trip, vs ~20% before. This impact is largely due to walking bikes along LTS 4 streets, which was incurring a several-minute penalty at each intersection; this was especially relevant downtown. It is somewhat concerning that the median changed so much, as I would have expected most routes to not have much bike walking anyways. 
- Minor changes to handling of contraflow lanes.

### Bike scenario

### `bike-all-lts1-37721.parquet`

- This regenerates the scenario to ensure it matches the same rules as the latest bicycle files

### `bike-scenario-6df8c.parquet`

- This fixes an issue where low-LTS one-way streets were treated as bikeable in both directions
- Elevation gain is now calculated over each 10m chunk of a segment, rather than as the delta from start to end. Many segments (between two consective OSM nodes) are less than 10m anyhow.

#### `bike-scenario-349e5.parquet`

- Initial addition of bicycle scenario

##### Known issues

- There are a handful of trips (~0.13%) where the bicycle scenario route (of everything LTS 1) actually takes marginally longer than the baseline route. I believe this has to do with intersection costs – in our weighting scheme, road crossings are more costly by bike than on foot, and there are some places where LTS was previously high enough that it required walking, and the cruise speed increase from switching to bike here is not enough to outweigh the longer crossing times.

### E-bike scenario

#### `bike-ebike-8a1a0-1.parquet`

The trips are about 13% faster than the all-LTS1 scenario, based on a few articles which are cited in the profile source code, and don’t avoid hills. It builds on the all-LTS 1 scenario, so there are no high-LTS roads in the network either. 

Note: This file differs from `bike-ebike-8a1a0.parquet` in that it adds distance by LTS. 

#### `bike-ebike-8a1a0.parquet`

- Initial addition of ebike scenario

### Car

#### `car-congestion-1d39c`

- Corrects an issue with traffic not being applied differentially by direction on two-way links

##### Known issues

- In a few places, StreetLight indicates that speeds are in excess of 90 mph, often on roads where that is unlikely to even be physically possible, e.g. https://www.openstreetmap.org/way/6042949 (this affects 31 out of 1.5 million segments on weekday mornings, haven’t checked other times but I imagine it’s similar). We could implement some kind of cap on speeds from StreetLight.

### Transit

#### `transit-trips-45d51`

- Adjusts when arrive-by routing is used; the following list is used to constrain the times (the end with the purpose in the list, or higher in the list, is constrained)
  1. Medical visit (e.g., doctor, dentist)
  1. Errand with appointment (e.g., haircut, accountant)
  1. Errand with appointment (e.g., haircut)
    
  1. K-12 school
  1. Attend K-12 school
  1. Daycare or preschool
  1. Attend daycare or preschool
  1. College/university
  1. Attend college/university
  1. Other education-related (e.g., field trip)
  1. Attend other education-related activity (e.g., field trip)
  1. Attend vocational education class
  1. Other type of class (e.g., cooking class)
  1. Attend other type of class (e.g., cooking class)
    
  1. Primary workplace
  1. Work-related activity (e.g., meeting, delivery, worksite)
  1. Went to work-related activity (e.g., meeting, delivery, worksite)
  1. Other work-related"

#### `transit-trips-7d58f`

- Adds circa 2019 MVTA GTFS to the routing. Upgrades to TransitRouter v0.2.1 to fix GTFS parsing issue with MVTA GTFS.

All trips that were possible before are still possible. Most have the same duration and arrival time. About 30,000 trips are newly possible. A non-trivial number of trips have a longer _duration_, because there is a better trip (earlier arrival for forward routing/later departure for reverse) that has a longer duration (e.g. an MVTA local bus that runs at the time you want to go, rather than a Metro Transit bus that runs later). A handful of trips have a later departure in the forward case/earlier arrival in the reverse case; these are trips that previously violated the constraints by up to five minutes, because doing so produced a trip 15 minutes better or more. With the new GTFS, there are now options that don't violate the constraints that are within 15 minutes of the options that do.

#### `transit-trips-93d71`, `transit-notransfer-93d71`

- Fixes an issue with overnight trips (trips that start on one day, but use transit vehicles running on the next), see [mattwigway/TransitRouter.jl#39](https://github.com/mattwigway/TransitRouter.jl/issues/39)

### Transit scenario

#### `transit-scenario-0277d`

- Adds MVTA to the transit scenario
- All cahnges from transit-trips 7d58f and 45d51

#### `transit-scenario-93d71`, `transit-notransfer-scenario-93d71`

- Initial addition of transit scenario

##### Known issues

- In most cases transit trips should be the same or better, however some have variations of a few seconds. I think this is due to OSRM not consistently returning the same access times, and am investigating. See `transit-scenario/transit_scenario_qc.qmd` in the repository for details.






