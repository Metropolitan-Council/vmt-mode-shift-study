import zipfile
import datetime
from collections import namedtuple
import pandas as pd
import numpy as np

GtfsFeed = namedtuple("GtfsFeed", [
    "routes", 
    "trips", 
    "stops", 
    "stop_times", 
    "calendar", 
    "calendar_dates", 
    "agency", 
    "shapes"
])

"""
Read a GTFS feed into a NamedTuple
"""
def read_gtfs(filename):
    with zipfile.ZipFile(filename) as z:
        with z.open("routes.txt") as c:
            routes = pd.read_csv(c, dtype={"route_id": "str"})
        with z.open("trips.txt") as c:
            trips = pd.read_csv(c, dtype={"shape_id": "str", "route_id": "str", "service_id": "str"}).set_index("trip_id")
        with z.open("stops.txt") as c:
            stops = pd.read_csv(c, dtype={"stop_id": "str"})
        with z.open("stop_times.txt") as c:
            stop_times = pd.read_csv(c, dtype={"stop_id": "str", "trip_id": "str"}).set_index(["trip_id", "stop_sequence"]).sort_index()
        with z.open("calendar.txt") as c:
            calendar = pd.read_csv(c, dtype={"service_id": "str"}).set_index("service_id")
        with z.open("calendar_dates.txt") as c:
            calendar_dates = pd.read_csv(c, dtype={"service_id": "str"})
            if len(calendar_dates) == 0:
                calendar_dates = pd.DataFrame({"service_id": [], "date": []})
            
            calendar_dates = calendar_dates.set_index(["service_id", "date"])
        with z.open("agency.txt") as c:
            agency = pd.read_csv(c)
        with z.open("shapes.txt") as c:
            shapes = pd.read_csv(c, dtype={"shape_id": "str"})
        
        return GtfsFeed(
            routes, 
            trips, 
            stops, 
            stop_times, 
            calendar, 
            calendar_dates, 
            agency, 
            shapes
        )
    
def write_gtfs(feed, filename):
    with zipfile.ZipFile(filename, "w") as z:
        with z.open("routes.txt", "w") as c:
            feed.routes.to_csv(c, index=False)

        with z.open("trips.txt", "w") as c:
            feed.trips.to_csv(c)

        with z.open("stops.txt", "w") as c:
            feed.stops.to_csv(c, index=False)

        with z.open("stop_times.txt", "w") as c:
            feed.stop_times.to_csv(c)

        with z.open("calendar.txt", "w") as c:
            feed.calendar.to_csv(c)

        with z.open("calendar_dates.txt", "w") as c:
            feed.calendar_dates.to_csv(c)

        with z.open("agency.txt", "w") as c:
            feed.agency.to_csv(c, index=False)

        with z.open("shapes.txt", "w") as c:
            feed.shapes.to_csv(c, index=False)


def gtfs_date_to_date(gtfsdate):
    return datetime.date(
        gtfsdate // 10000,
        (gtfsdate % 10000) // 100,
        (gtfsdate % 100)
    )

def service_running(feed, date, service):    
    # check calendar_dates.txt
    if (service, date) in feed.calendar_dates.index:
        return feed.calendar_dates.at[(service, date), "exception_type"] == 1
    
    # check calendar.txt
    dateobj = gtfs_date_to_date(date)
    # Note: this will only work in en_US locale (or other locale with english day names)
    dow = dateobj.strftime("%A").lower()
    
    if service in feed.calendar.index:
        return feed.calendar.at[service, dow] == 1 and date >= feed.calendar.at[service, "start_date"] and date <= feed.calendar.at[service, "end_date"]
    
    # if we're here, not in calendar or calendar_dates
    return False

# can't use built in Python time parsing, times exceed 24 hours
def gtfs_time_to_seconds(gtfstime):
    if pd.isnull(gtfstime):
        return np.nan
    
    h, m, s = gtfstime.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)

def seconds_to_gtfs_time(seconds):
    if pd.isnull(seconds):
        return seconds
    
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    
    return f"{h:02d}:{m:02d}:{s:02d}"