import numpy as np
import pandas as pd
import geopandas as gpd
from ast import literal_eval
import streamlit as st

from steps.mode_enum import Mode

from settings import handler

def clean_mode_names(df: pd.DataFrame):
    print("cleaning mode names")
    df["mode"] = np.where(df["mode"] == "Car", Mode.CAR, df["mode"])
    df["mode"] = np.where(df["mode"] == "Transit", Mode.TRANSIT, df["mode"])
    df["mode"] = np.where(df["mode"] == "Bike/Scooter", Mode.BIKE, df["mode"])
    df["mode"] = np.where(df["mode"] == "Walk", Mode.WALK, df["mode"])

def merge_weather(df: pd.DataFrame):
    print("merging in weather")
    # reading in weather data
    # https://www.ncei.noaa.gov/pub/data/ghcn/daily/
    weather = pd.read_csv("data/" + handler["weather_file_name"])
    weather = weather[["Date", "Measurement", "Value"]]
    weather = weather.pivot(index="Date", columns="Measurement", values="Value")
    
    weather["year"] = weather.index.astype(str).str[0:4]
    weather["month"] = weather.index.astype(str).str[4:6]
    weather["day"] = weather.index.astype(str).str[6:8]
    weather["date"] = weather["year"] + "-" + weather["month"] + "-" + weather["day"]
    weather = weather.set_index("date")
    
    # see https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt for a key
    df["temperature"] = (weather.loc[df["travel_date"].values, "TAVG"] / 10).values # average temperature in Celsius
    df["precipitation"] = (weather.loc[df["travel_date"].values, "PRCP"] / 10).values # precipition in mm
    df["snowfall"] = (weather.loc[df["travel_date"].values, "SNOW"] / 10).values # snowfall in mm
    df["temperature_max"] = (weather.loc[df["travel_date"].values, "TMAX"] / 10).values # average temperature in Celsius
    df["temperature_min"] = (weather.loc[df["travel_date"].values, "TMIN"] / 10).values # average temperature in Celsius
    df["precipitation"] = (weather.loc[df["travel_date"].values, "PRCP"] / 10).values # precipition in mm
    df["snow_depth"] = (weather.loc[df["travel_date"].values, "SNWD"] / 10).values # snowfall in mm
    
def transit_cleanup(transit):
    print("cleanup on transit")
    # calculate duration from star/tend times
    transit["start_time_dt"] = pd.to_datetime(transit["start_time"])
    transit["end_time_dt"] = pd.to_datetime(transit["end_time"])

    # transit["duration"] = (transit["end_time_dt"] - transit["start_time_dt"]).apply(lambda x: x.seconds / 60)
    
    transit["num_transfers"] = (transit["leg_type"] == "TransitRouter.transfer") # temporary field to calculate number of transfers
    transit["non_transit_duration"] = (transit["leg_type"].isin(["TransitRouter.access", "TransitRouter.egress"])) * (transit["end_time_dt"] - transit["start_time_dt"]).apply(lambda x: x.seconds / 60) # non-transit time (access and egress)
    
    # project to US equidistant projection to calculate lengths of paths (in meters)
    # https://spatialreference.org/ref/esri/usa-contiguous-equidistant-conic/
    transit.crs = "EPSG:4326"
    transit = transit.to_crs("EPSG:32615")
    
    transit["length"] = transit.length
    transit["access_length"] = transit["length"]
    
    # create a gdf for linked trips
    agg_fns = {
        "trip_id": "first",
        "leg_index": "count",
        "start_time": "first",
        "end_time": "last",
        "origin_stop_id": "first", # throw away
        "origin_stop_name": "first",
        "destination_stop_id": "first",
        "destination_stop_name": "first",
        "route_id": "first", 
        "route_short_name": "first",
        "route_long_name": "first",
        "route_type": "first", 
        "leg_type": "first", # end throw away
        "start_time_dt": "first",
        "end_time_dt": "last",
        "length": "sum",
        "access_length": "first",
        "num_transfers": "sum",
        "non_transit_duration": "sum"
    }
    
    transit_grouped = transit.dissolve(by="trip_id", aggfunc=agg_fns) # merges geometries in addition to aggregating the rest of the columns
    transit_grouped["duration"] = (transit_grouped["end_time_dt"] - transit_grouped["start_time_dt"]).apply(lambda x: x.seconds / 60)

    return transit_grouped 

def merge_transit_trip_details(df: pd.DataFrame, data_dir: str):
    print("merging in transit details from raw tbi data")
    # read in raw tbi data
    wave1_trips = pd.read_csv(handler["drive_data_dir"] + "/Data/TBI Wave 1 Dataset 20200630/trip.csv")
    wave2_trips = pd.read_csv(handler["drive_data_dir"] + "/Data/Wave 2 Data Deliverable/trip.csv")
    raw_trips = pd.concat([wave1_trips, wave2_trips]).set_index("trip_id")
    
    def get_dist_to_stop(trips, wave): # calculate distance to get to stop to start transit trip
        target = raw_trips.loc[trips[0]] # consider the first trip of the linked trip
        # if the purpose of the trip is to switch modes and the mode type is not to switch modes and the distance is not none, return it
        if target["d_purpose_category"] in [10, 11] and (wave == 1 and target["mode_type"] not in [1, 3, 4] or wave == 2 and target["mode_type"] not in [12, 13, 14]):
            if not np.isnan(target["distance"]):
                return target["distance"]
        # otherwise assume that transit can be reached in 0.1 miles
        return 0.1
    
    df["est_observed_transit_access_dist"] = 0
    df.loc[df["mode"] == "Transit", "est_observed_transit_access_dist"] = df[df["mode"] == "Transit"].apply(lambda x: get_dist_to_stop(literal_eval(x["trip_id"]), x["wave"]), axis=1)
    
    # this function estimates the number of transfers a transit trip would go on
    # the main source of error are inconsistencies with linked trips--e.g., having two trips that should be one linked trip put into two separate linked trips
    # another source of error is counting the access trip as implicitly one transfer occasionally
    def get_num_transfers(trips, wave):
        res = 0
        for trip in trips:
            # count the number of trips whose destination purposes are to change mode
            if wave == 2 and raw_trips.loc[trip]["d_purpose_category"] == 11 or \
                wave == 1 and raw_trips.loc[trip]["d_purpose_category"] == 10:
                res += 1
        return res
    
    df["transfers"] = 0
    df.loc[df["mode"] == "Transit", "transfers"] = df[df["mode"] == "Transit"].apply(lambda x: get_num_transfers(literal_eval(x["trip_id"]), x["wave"]), axis=1)
    
def add_community(df: pd.DataFrame):
    print("adding communities")
    communities = gpd.read_file("data/" + handler["community_shape_file_name"]).to_crs("EPSG:4326")
    
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["home_lon"], df["home_lat"]), crs="EPSG:4326")
    
    df["community"] = -1
    for i, row in communities.iterrows():
        df["community"] = np.where(gdf["geometry"].within(row["geometry"]), row.name, df["community"])

def prepare_csv(df: pd.DataFrame, data_dir: str):
    merge_weather(df)

    print("reading in rerouting files")
    car = pd.read_parquet(data_dir + "/Data_Processed/geodata/car_congestion_nogeom.parquet")
    bike = pd.read_parquet(data_dir + "/Data_Processed/geodata/bike_no_weight_penalty.parquet").drop("geometry", axis=1)
    transit = gpd.read_parquet(data_dir + "/Data_Processed/geodata/transit_trips.parquet")
    walk = pd.read_parquet(data_dir + "/Data_Processed/geodata/walk_trips_nogeom.parquet")
    
    transit_grouped = transit_cleanup(transit)
    
    print("merging rerouting to dataframe")
    # rename columns to distinguish by mode
    def add_mode_to_column_name(mode_df, mode_name): 
        renames = {}
        for col in mode_df.columns:
            renames[col] = mode_name + '_' + col
        return mode_df.rename(columns = renames)

    car = add_mode_to_column_name(car, 'car')
    walk = add_mode_to_column_name(walk, 'walk')
    bike = add_mode_to_column_name(bike, 'bike')
    transit = add_mode_to_column_name(transit_grouped, 'transit')
    
    def get_car_data(row, field):
        hour = int(row["arrive_time"][0:2])
        sunday = row["travel_dow"] == "Sunday"
        saturday = row["travel_dow"] == "Saturday"
        if sunday:
            query = "sundays"
        elif saturday:
            query = "saturdays_"
        else:
            query = "weekdays_"
        
        if hour >= 0 and hour <= 5:
            query += "0-6"
        elif hour >= 20 and hour <= 23:
            query += "20-24"
        else:
            query += str(hour) + "-" + str(hour + 1)

        if (query, row["trip_id"]) not in car.index:
            print(row["trip_id"])
            return np.nan

        return car.loc[(query, row["trip_id"])][field]
    
    # missing one trip for some reason
    df["car_duration_seconds"] = df.apply(lambda x: get_car_data(x, "car_duration_seconds"), axis=1)
    df["car_distance_meters"] = df.apply(lambda x: get_car_data(x, "car_distance_meters"), axis=1)
    
    df = df.merge(walk, left_on="trip_id", right_on="walk_trip_id", how="left")
    df = df.merge(bike, left_on="trip_id", right_on="bike_trip_id", how="left")
    df = df.merge(transit.drop("transit_geometry", axis=1), left_on="trip_id", right_on="transit_trip_id", how="left")
    
    # everything is feasible initially
    df[f'feasible_{Mode.WALK}_shift'] = True
    df[f'feasible_{Mode.BIKE}_shift'] = True
    df[f'feasible_{Mode.TRANSIT}_shift'] = True
    df['feasible_shift'] = True
    
    merge_transit_trip_details(df, data_dir)
    
    add_community(df)
    
    clean_mode_names(df)
    
    # possibly change to provided name
    df.to_csv("data/tbi_full.csv")
    
    return df