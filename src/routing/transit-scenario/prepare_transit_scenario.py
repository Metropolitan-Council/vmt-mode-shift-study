"""
This prepares the GTFS for the transit scenario, based on the existing GTFS feed.
It roughly doubles service in the GTFS feed. The following algorithm is applied sequentially for
each day of the week.

For each route-direction, we first find the most common stop (i.e. the stop that is served by the most
trips on that service day by that route and direction. Generally there will be ties; the one that occurs
first in the pattern is used as the "reference stop". Most of the time, this will be a stop that is common
to all patterns. The script will warn about the few cases where it is not (why this is important is discussed
below).

Then, we identify the first time each trip departs the reference stop, and sort trips by this time. We use the reference
stop rather than the time at the first stop, because the first stop may be very different on different trips; if there
is a short-turn, for example, a trip that logical person would call "later" may leave the first stop _of that trip_ earlier.

Then, we duplicate each trip and shift it forward in time so that it passes the reference stop half way between the time
of the original trip and the next trip on the route-direction. If there is no next trip on the route-direction (i.e. it is
the last trip of the day), or if the trip does not pass the reference stop, it is not duplicated but is passed through into
the output unmodified.

To simplify the algorithm, it is applied separately to each day of a "reference week", and all trips running that day are copied into the output,
duplicated as described above. The calendar is then replaced with a trivial calendar with service_ids monday, tuesday, ... which are
exactly what you would expect - the monday service runs on monday, etc.
"""

import pandas as pd
from collections import defaultdict
from functools import partial
from sys import argv
from gtfsutil import GtfsFeed, read_gtfs, write_gtfs, gtfs_date_to_date, gtfs_time_to_seconds, seconds_to_gtfs_time, service_running

# Note that this is different than specified in the Julia file, because the Julia
# date finding is exclusive (i.e. does not include the start) while Python is inclusive.
REFERENCE_WEEK_START = 20191020

"Find the most common stop among a set of trips"
def most_common_stop(feed, trip_ids):
    stop_counts = defaultdict(lambda: 0)
    
    for trip_id in trip_ids:
        for stop in feed.stop_times.loc[trip_id, "stop_id"]:
            stop_counts[stop] += 1
            
    # find the most popular stop
    most_trips = max(stop_counts.values())
    
    # find the first common stop. It may not be present on the first trip
    for trip_id in trip_ids:
        for stop in feed.stop_times.loc[trip_id, "stop_id"]:
            if stop_counts[stop] == most_trips:
                return stop
    else:
        raise ValueError(f"Did not find any stops with max stop count {most_trips}, trip_ids {trip_ids}")

def process_feed(feed):
    new_trips = []
    new_stoptimes = []

    for date in range(REFERENCE_WEEK_START, REFERENCE_WEEK_START + 7):
        day_of_week = gtfs_date_to_date(date).strftime("%A").lower()
        print(f"Processing {day_of_week}, {date}")

        # get running trips
        running_trips = feed.trips[feed.trips.service_id.apply(partial(service_running, feed, date))].copy()

        # remove trips with no stop times
        running_trips["n_stop_times"] = feed.stop_times.groupby("trip_id").size().reindex(running_trips.index, fill_value=0)
        running_trips = running_trips[running_trips.n_stop_times > 0].copy()
        running_trips.drop(columns="n_stop_times", inplace=True)

        # find the most common/reference stop on each trip
        common_stop = (
            running_trips
                .reset_index()
                .groupby(["route_id", "direction_id"]).trip_id.apply(partial(most_common_stop, feed)).rename("most_common_stop").reset_index())
        
        running_trips = running_trips.reset_index().merge(common_stop, how="left", on=["route_id", "direction_id"], validate="m:1")

        # find the first time at the stop
        # trips may visit the same stop twice. Get the first time they visit, use that to align trips.
        first_time_at_stop = feed.stop_times.groupby(["trip_id", "stop_id"]).departure_time.first().apply(gtfs_time_to_seconds)
        running_trips = (
            running_trips
            .merge(first_time_at_stop.rename("time_at_reference_stop"),
                                            left_on=["trip_id", "most_common_stop"], right_index=True, how="left", validate="1:1")
        )

        n_missing_reference_stop = sum(running_trips.time_at_reference_stop.isnull())
        print(f"WARN: {n_missing_reference_stop} ({n_missing_reference_stop / len(running_trips) * 100:.1f}%) trips are missing the reference stop for their route-direction")

        # now do the duplication. First, sort the trips so we can iterate
        running_trips = running_trips.sort_values(["route_id", "direction_id", "time_at_reference_stop"])


        running_trips["next_time_at_ref_stop"] = running_trips.time_at_reference_stop.shift(-1)
        running_trips["next_route_id"] = running_trips.route_id.shift(-1)
        running_trips["next_direction_id"] = running_trips.direction_id.shift(-1)
        running_trips["next_trip_id"] = running_trips.trip_id.shift(-1)

        for _, trip in running_trips.iterrows():
            newtrip = trip.copy()
            # to avoid confusion with overlapping service, etc, we just create a new simple calendar file
            newtrip["service_id"] = "wednesday"
            origtripid = newtrip["trip_id"]
            newtrip["trip_id"] = origtripid + "_original_" + day_of_week
            
            new_trips.append(newtrip)
            
            stoptimes = feed.stop_times.loc[origtripid].reset_index().copy()
            stoptimes["trip_id"] = newtrip.trip_id
            new_stoptimes.append(stoptimes)
            
            # if we're in the middle of the day
            if not pd.isnull(newtrip.time_at_reference_stop) and newtrip["route_id"] == newtrip["next_route_id"] and newtrip["direction_id"] == newtrip["next_direction_id"]:
                dupetrip = newtrip.copy()
                dupetrip["trip_id"] = origtripid + "_duplicate_" + day_of_week
                new_trips.append(dupetrip)
                
                # find the headway at the reference stop
                headway = newtrip.next_time_at_ref_stop - newtrip.time_at_reference_stop
                
                if headway == 0:
                    print(f"WARN: trip IDs {origtripid} and {newtrip.next_trip_id} arrive at the reference stop {newtrip.most_common_stop} at the same time")
                else:
                    dupe_stoptimes = stoptimes.copy()
                    dupe_stoptimes["trip_id"] = dupetrip["trip_id"]
                    dupe_stoptimes["arrival_time"] = (dupe_stoptimes.arrival_time.apply(gtfs_time_to_seconds) + headway / 2).astype("Int64").apply(seconds_to_gtfs_time)
                    dupe_stoptimes["departure_time"] = (dupe_stoptimes.departure_time.apply(gtfs_time_to_seconds) + headway / 2).astype("Int64").apply(seconds_to_gtfs_time)
                    new_stoptimes.append(dupe_stoptimes)

    # end loop over days
    
    # put the feed together
    new_stoptimes = pd.concat(new_stoptimes)
    new_trips = pd.DataFrame(new_trips, index=None)
    
    new_calendar = []

    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for day in days:
        new_calendar.append(pd.Series([day, 20190101, 20231231, *[1 if day == d else 0 for d in days]],
                                    index=["service_id", "start_date", "end_date", *days]))
        
    new_calendar = pd.DataFrame(new_calendar)

    return GtfsFeed(
        feed.routes,
        new_trips.set_index("trip_id"),
        feed.stops,
        new_stoptimes.set_index(["trip_id", "stop_sequence"]),
        new_calendar.set_index("service_id"),
        pd.DataFrame(),
        feed.agency,
        feed.shapes
    )

if __name__ == "__main__":
    inf = argv[1]
    outf = argv[2]

    feed = read_gtfs(inf)
    processed = process_feed(feed)
    write_gtfs(processed, outf)