import numpy as np
import pandas as pd
import geopandas as gpd
from ast import literal_eval
import streamlit as st
import keyring
import logging

from steps.enums import Mode

from settings import handler

def clean_mode_names(df: pd.DataFrame):
    logging.info("cleaning mode names")
    df["mode"] = np.where(df["mode"] == "Car", Mode.CAR, df["mode"])
    df["mode"] = np.where(df["mode"] == "Transit", Mode.TRANSIT, df["mode"])
    df["mode"] = np.where(df["mode"] == "Bike/Scooter", Mode.BIKE, df["mode"])
    df["mode"] = np.where(df["mode"] == "Walk", Mode.WALK, df["mode"])

def merge_weather(df: pd.DataFrame):
    logging.info("merging in weather")
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
    logging.info("cleanup on transit")
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

    return transit_grouped[["trip_id", "duration", "access_length", "num_transfers", "non_transit_duration", "length"]]

def merge_transit_trip_details(df: pd.DataFrame, data_dir: str):
    logging.info("merging in transit details from raw tbi data")
    drive_data_dir = keyring.get_password('msp', 'vmt_reduction_dir')
    
    # read in raw tbi data
    wave1_trips = pd.read_csv(drive_data_dir + "/Data/TBI Wave 1 Dataset 20200630/trip.csv")
    wave2_trips = pd.read_csv(drive_data_dir + "/Data/Wave 2 Data Deliverable/trip.csv")
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
    logging.info("adding communities")
    communities = gpd.read_file("data/" + handler["community_shape_file_name"]).to_crs("EPSG:4326").set_index("CTU_NAME")
    
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["home_lon"], df["home_lat"]), crs="EPSG:4326")
    
    df["community"] = "na"
    for _, row in communities.iterrows():
        df["community"] = np.where(gdf["geometry"].within(row["geometry"]), row.name, df["community"])
        
def final_field_cleanup(df: pd.DataFrame):
    df["purpose_cleaned"] = df["d_purpose_category"]
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"] == "Home", df["o_purpose_category"], df["purpose_cleaned"])
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["School", "School-related", "School related"]), "School", df["purpose_cleaned"])
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Work", "Work-related", "Work related"]), "Work", df["purpose_cleaned"])
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Errand/Other", "Errand"]), "Errand", df["purpose_cleaned"])
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Shop", "Shopping"]), "Shop", df["purpose_cleaned"])
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Other", "Change mode", "Overnight", "Spent the night at non-home location"]), "Other", df["purpose_cleaned"])
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Missing: Non-response", "Missing: Skip logic", "Not imputable", "Missing", "Missing: Non-imputable"]), "Missing", df["purpose_cleaned"])
    
    df["child"] = df["age"].isin(["5-15", "5 to 15", "16-17", "16 to 17", "Under 5"])
    df["senior"] = df["age"].isin(["65-74", "65 to 74", "75 or older", "75 to 84", "85 or older"])
    df["student"] = ~df["student_status"].str.contains("No")
    df["unemployed"] = df["job_type"].str.contains("Missing")
    df["parent"] = df["num_kids"] != 0
        
    df["person_type"] = "na"
    df["person_type"] = np.where(df["child"], "child", df["person_type"])
    df["person_type"] = np.where(~df["unemployed"] & df["parent"], "working adult with kids", df["person_type"])
    df["person_type"] = np.where(df["unemployed"] & df["parent"], "non-working adult with kids", df["person_type"])
    df["person_type"] = np.where(~df["unemployed"] & ~df["parent"], "working adult without kids", df["person_type"])
    df["person_type"] = np.where(df["unemployed"] & ~df["parent"], "non-working adult without kids", df["person_type"])
    df["person_type"] = np.where(df["senior"] & df["unemployed"], "retired", df["person_type"])
    df["person_type"] = np.where((~df["child"]) & (df["student"]), "college student", df["person_type"]) # if placed above, everything else overwrites it
    
    df["gender_cleaned"] = df["gender"]
    df["gender_cleaned"] = np.where(df["gender_cleaned"] == "Other/prefer to self-describe", "Other/Prefer to self-describe", df["gender_cleaned"])
    
    df["income_detailed"] = np.where(df["income_detailed"].isin(set(["Less than $15,000", "Under $15,000"])), "Under $15,000", df["income_detailed"])
    df["income_detailed"] = np.where(df["income_detailed"] == "Prefer not to answer", "na", df["income_detailed"])
    
def add_terminal_times(df: pd.DataFrame):
    logging.info("adding terminal times for tazs")
    tazs = gpd.read_file("data/" + handler["taz_terminal_time_file_name"]).to_crs("EPSG:4326")
    
    o_gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["o_lon"], df["o_lat"]), crs="EPSG:4326")
    d_gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["d_lon"], df["d_lat"]), crs="EPSG:4326")
    
    df["o_car_terminal_time"] = 0
    df["d_car_terminal_time"] = 0
    
    for _, row in tazs[~tazs["TAZ"].isna()].iterrows():
        df["o_car_terminal_time"] = np.where(o_gdf["geometry"].within(row["geometry"]), row["TERM_TIME"], df["o_car_terminal_time"])
        df["d_car_terminal_time"] = np.where(d_gdf["geometry"].within(row["geometry"]), row["TERM_TIME"], df["d_car_terminal_time"])
        
    df["car_duration_seconds_adj"] = df["car_duration_seconds"] + 60 * df["o_car_terminal_time"] + 60 * df["d_car_terminal_time"]
    df["bike_duration_seconds_adj"] = df["bike_duration_seconds"] + 120
    
def round_off_columns(df: pd.DataFrame):
    logging.info("rounding off columns")
    
    df["car_duration_seconds"] = df["car_duration_seconds"].round()
    df["car_distance_meters"] = df["car_distance_meters"].round()
    
    df["walk_duration_seconds"] = df["walk_duration_seconds"].round()
    df["walk_distance_meters"] = df["walk_distance_meters"].round()
    
    df["bike_duration_seconds"] = df["bike_duration_seconds"].round()
    df["bike_distance_meters"] = df["bike_distance_meters"].round()
    df["bike_distance_meters_1"] = df["bike_distance_meters_1"].round()
    df["bike_distance_meters_2"] = df["bike_distance_meters_2"].round()
    df["bike_distance_meters_3"] = df["bike_distance_meters_3"].round()
    df["bike_distance_meters_4"] = df["bike_distance_meters_4"].round()
    
    df["transit_duration"] = df["transit_duration"].round()
    df["transit_length"] = df["transit_length"].round()
    df["transit_access_length"] = df["transit_access_length"].round()
    
@st.cache_data()
def prepare_data(df: pd.DataFrame, data_dir: str):
    logging.info("beginning data intake and cleaning")
    merge_weather(df)

    logging.info("reading in rerouting files")
    car = pd.read_parquet(data_dir + "/Data_Processed/geodata/car_congestion_nogeom.parquet")
    bike = pd.read_parquet(data_dir + "/Data_Processed/geodata/bike_no_weight_penalty.parquet").drop("geometry", axis=1)
    transit = gpd.read_parquet(data_dir + "/Data_Processed/geodata/transit_trips.parquet")
    walk = pd.read_parquet(data_dir + "/Data_Processed/geodata/walk_trips_nogeom.parquet")
    
    transit_grouped = transit_cleanup(transit)
    
    logging.info("merging rerouting to dataframe")
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
    df = df.merge(transit, left_on="trip_id", right_on="transit_trip_id", how="left")
    
    merge_transit_trip_details(df, data_dir)
    
    add_community(df)
    
    clean_mode_names(df)
    
    final_field_cleanup(df)
    
    add_terminal_times(df)
    
    round_off_columns(df)
    
    logging.info("exporting newly created table to csv")
    # possibly change to provided name
    df.to_csv("data/tbi_full.csv", index=False)
    
    return df