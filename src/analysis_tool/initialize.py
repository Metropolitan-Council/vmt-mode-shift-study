"""
This initialization file is used to take in multiple sources of data and create an input file compatible with the TBI tool

The code/cleanup here will be dependent on the exact types of data used in the TBI (as of 9/12, it works for the cleaned wave1/2 TBI inputs along with the associated rerouting files/weather data/CTU shape file), but the requirements for what the input should actually have are described in the config.yml file (and the mappings between the created cleaned df and these input columns should be defined).

This is the only place of the tool where non-standardized column names should be used; after cleanup, the column names should be standardized according to the schema outlined in the config.yml. New columns can still be created/referenced within the tool, but they will not persist. 
"""


import numpy as np
import pandas as pd
import geopandas as gpd
from ast import literal_eval
import streamlit as st
import keyring
import logging
from settings import get_communities
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
import itertools

from steps.enums import Mode

from settings import handler

dir = keyring.get_password("msp", "vmt_reduction_dir")
MILES_PER_METER = 0.000621371

# # helper function for querying from the car rerouting file
def get_car_data(row, field, car_df):
    hour = int(row["arrive_time"][0:2])
    sunday = row["travel_dow"] == "Sunday"
    saturday = row["travel_dow"] == "Saturday"
    if sunday:
        query = "sundays_"
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

    if (query, row["trip_id"]) not in car_df.index:
        print(row["trip_id"])
        return np.nan

    return car_df.loc[(query, row["trip_id"])][field]

dir = keyring.get_password("msp", "vmt_reduction_dir")
MILES_PER_METER = 0.000621371

# # helper function for querying from the car rerouting file
def get_car_data(row, field, car_df):
    hour = int(row["arrive_time"][0:2])
    sunday = row["travel_dow"] == "Sunday"
    saturday = row["travel_dow"] == "Saturday"
    if sunday:
        query = "sundays_"
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

    if (query, row["trip_id"]) not in car_df.index:
        print(row["trip_id"])
        return np.nan

    return car_df.loc[(query, row["trip_id"])][field]

def clean_mode_names(df: pd.DataFrame) -> None:
    """
    This function standardizes the mode names based on the defined mode enum in-place.
    """
    logging.info("cleaning mode names")
    df["mode"] = np.where(df["mode"] == "Car", Mode.CAR, df["mode"])
    df["mode"] = np.where(df["mode"] == "Transit", Mode.TRANSIT, df["mode"])
    df["mode"] = np.where(df["mode"] == "Bike/Scooter", Mode.BIKE, df["mode"])
    df["mode"] = np.where(df["mode"] == "Walk", Mode.WALK, df["mode"])

def merge_weather(df: pd.DataFrame) -> None:
    """
    This function merges in the weather df from handler['weather_file_name'] into the main df in-place.
    """
    logging.info("merging in weather")
    # reading in weather data
    # https://www.ncei.noaa.gov/pub/data/ghcn/daily/
    weather = pd.read_csv("data/" + handler["weather_file_name"], low_memory=False)
    weather = weather[["Date", "Measurement", "Value"]]
    weather = weather.pivot(index="Date", columns="Measurement", values="Value")
    
    # get useful date columns and set that as the index
    weather["year"] = weather.index.astype(str).str[0:4]
    weather["month"] = weather.index.astype(str).str[4:6]
    weather["day"] = weather.index.astype(str).str[6:8]
    weather["date"] = weather["year"] + "-" + weather["month"] + "-" + weather["day"]
    weather = weather.set_index("date")
    
    # see https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt for a key
    # merge in temperature/atmospheric indicator into df by querying weather with a list of dates from df
    df["temperature"] = (weather.loc[df["travel_date"].values, "TAVG"] / 10).values # average temperature in Celsius
    df["precipitation"] = (weather.loc[df["travel_date"].values, "PRCP"] / 10).values # precipition in mm
    df["snowfall"] = (weather.loc[df["travel_date"].values, "SNOW"] / 10).values # snowfall in mm
    df["temperature_max"] = (weather.loc[df["travel_date"].values, "TMAX"] / 10).values # average temperature in Celsius
    df["temperature_min"] = (weather.loc[df["travel_date"].values, "TMIN"] / 10).values # average temperature in Celsius
    df["precipitation"] = (weather.loc[df["travel_date"].values, "PRCP"] / 10).values # precipition in mm
    df["snow_depth"] = (weather.loc[df["travel_date"].values, "SNWD"] / 10).values # snowfall in mm
    
def transit_cleanup(transit) -> pd.DataFrame:
    """
    This function does some basic clean up on the transit df before it is merged into the main df dataframe. 

    Args:
        transit (DataFrame): the initial non-cleaned transit dataframe

    Returns:
        DataFrame : the cleaned up dataframe
    """
    logging.info("cleanup on transit")
    # calculate duration from star/tend times
    transit["start_time_dt"] = pd.to_datetime(transit["start_time"])
    transit["end_time_dt"] = pd.to_datetime(transit["end_time"])
    
    # project to US equidistant projection to calculate lengths of paths (in meters)
    # https://spatialreference.org/ref/esri/usa-contiguous-equidistant-conic/
    transit.crs = "EPSG:4326"
    transit = transit.to_crs("EPSG:32615")    
    
    transit["num_transfers"] = (transit["leg_type"] == "TransitRouter.transfer") # temporary field to calculate number of transfers
    transit["num_boardings"] = (transit["leg_type"] == "TransitRouter.transit") # temporary field to verify that a boarding happens
    
    transit["access_dist_mi"] = np.where(transit['leg_type'] == 'TransitRouter.access', transit["distance_meters"] / 1609.34, 0)
    transit["egress_dist_mi"] = np.where(transit['leg_type'] == 'TransitRouter.egress', transit["distance_meters"] / 1609.34, 0)
        
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
        "access_dist_mi": "sum",
        "egress_dist_mi": "sum",
        "num_transfers": "sum", 
        "num_boardings": "sum"
    }
    
    # branching logic for whether we need to calculate distances ourselves based on projection
    if "distance_meters" in transit.columns:
        transit["length"] = transit["distance_meters"]
    else:
        transit["length"] = transit.length
        
    transit["access_length"] = transit["length"]
        
    # group transit (which are initially unlinked trips) into linked trips
    transit_grouped = transit.dissolve(by="trip_id", aggfunc=agg_fns) # merges geometries in addition to aggregating the rest of the columns
    transit_grouped["non_wait_duration"] = (transit_grouped["end_time_dt"] - transit_grouped["start_time_dt"]).apply(lambda x: x.seconds / 60)

    # return the grouped transit dataframe 
    return transit_grouped[["trip_id", "start_time_dt", "end_time_dt", "non_wait_duration", "access_dist_mi", "egress_dist_mi", "num_transfers", "num_boardings"]]

def time_diff(row): 
    """
    Given a row of a dataframe, calculates and returns the transit wait time. 
    """
    
    # for work, we so you arrive at work on time
    if row['d_purpose_category']=="Work":
        wait_time = (row['arrive_time_dt'] - row['transit_end_time_dt']).seconds / 60
    else:
        wait_time = (row['transit_start_time_dt'] - row['depart_time_dt']).seconds / 60
    
    # we allow trips to depart up to 5 minutes early or arrive up to 5 minutes late
    # if it saves at least 15 minutes of travel time.  Therefore, some calculated 
    # wait times are offset
    if wait_time >= 1435: 
        wait_time = 1440-wait_time
        
    return wait_time

def add_transit_wait_time(df: pd.DataFrame) -> None: 
    """
    The router provides a transit_start_time and transit_end_time based on when you have to leave to catch the bus. 
    If someone leaves earlier than that based on their schedule, this method countsthe difference between the 
    desired departure time and the required departure time as waiting time.  It then includes the waiting time in the 
    transit duration. 
    """

    df["depart_time_dt"] = pd.to_datetime(df['depart_time'], format="%H:%M:%S")
    df["arrive_time_dt"] = pd.to_datetime(df['arrive_time'], format="%H:%M:%S")
    df["transit_wait_time"] = df.apply(time_diff, axis=1)
    df["transit_duration"] = df["transit_non_wait_duration"] + df["transit_wait_time"]
    

def merge_transit_trip_details(df: pd.DataFrame, data_dir: str) -> None:
    """
    This function does some processing on the raw TBI data to estimate various details about transit trips -- distance to stop/num transfers -- and merges this into df in-place.
    """
    logging.info("merging in transit details from raw tbi data")
    
    # read in raw tbi data
    wave1_trips = pd.read_csv(data_dir + "/Data/TBI Wave 1 Dataset 20200630/trip.csv", low_memory=False)
    wave2_trips = pd.read_csv(data_dir + "/Data/Wave 2 Data Deliverable/trip.csv", low_memory=False)
    raw_trips = pd.concat([wave1_trips, wave2_trips]).set_index("trip_id")
    
    def get_dist_to_stop(trips, wave): # calculate distance to get to stop to start transit trip
        target = raw_trips.loc[trips[0]] # consider the first trip of the linked trip
        # if the purpose of the trip is to switch modes and the mode type is not to switch modes and the distance is not none, return it
        if target["d_purpose_category"] in [10, 11] and (wave == 1 and target["mode_type"] not in [1, 3, 4] or wave == 2 and target["mode_type"] not in [12, 13, 14]):
            if not np.isnan(target["distance"]):
                return target["distance"]
        # otherwise assume that transit can be reached in 0.1 miles
        return 0.1
    
    # fill in df with estimated transit access distance based on results of above function into
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
    
    # fill in df with estimated transfer count based on above function
    df["transfers"] = 0
    df.loc[df["mode"] == "Transit", "transfers"] = df[df["mode"] == "Transit"].apply(lambda x: get_num_transfers(literal_eval(x["trip_id"]), x["wave"]), axis=1)
    
def add_CTU(df: pd.DataFrame) -> None:
    """
    This function adds communities to each unlinked trip of the dataframe based on the trip's origin latlon.
    """
    logging.info("adding communities")
    
    # read in communities
    communities = get_communities()

    # convert df to a geodataframe using origin lat/lon of trip
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["o_lon"].fillna(0), df["o_lat"].fillna(0)), crs="EPSG:4326")
    
    # do sjoin to determine what CTU each olon/olat point of df is in
    df["CTU"] = (
        gpd.sjoin(gdf[["geometry"]], communities.reset_index(), how="left")
        .reset_index()
        .groupby("index")  # after sjoin, some things map to multiple geometries, so we deduplicate by grouping by idx and taking the first of each one
        .first()
        ["CTU_NAME"]
        .fillna("na")  # if nothing matches, is not in any CTU
        .values
    )
        
def final_field_cleanup(df: pd.DataFrame) -> None:
    """
    This function does some in-place final cleanups on dataframe.
    """
    
    # clean up purpose
    df["purpose_cleaned"] = df["d_purpose_category"]
    # if the d_purpose is home, change it to the o_purpose
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"] == "Home", df["o_purpose_category"], df["purpose_cleaned"])
    # merging of similar purposes into one
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["School", "School-related", "School related"]), "School", df["purpose_cleaned"])
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Work", "Work-related", "Work related"]), "Work", df["purpose_cleaned"])
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Errand/Other", "Errand"]), "Errand", df["purpose_cleaned"])
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Shop", "Shopping"]), "Shop", df["purpose_cleaned"])
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Other", "Change mode", "Overnight", "Spent the night at non-home location"]), "Other", df["purpose_cleaned"])
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Missing: Non-response", "Missing: Skip logic", "Not imputable", "Missing", "Missing: Non-imputable"]), "Other", df["purpose_cleaned"])
    df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Home"]), "Other", df["purpose_cleaned"])  # a few home-to-home trips -> group with other
    
    # creation of person categories based on various categories of age/employment/student status
    df["child"] = df["age"].isin(["5-15", "5 to 15", "16-17", "16 to 17", "Under 5"])
    df["senior"] = df["age"].isin(["65-74", "65 to 74", "75 or older", "75 to 84", "85 or older"])
    df["student"] = ~df["student_status"].str.contains("No")
    df["unemployed"] = df["job_type"].str.contains("Missing")
    df["parent"] = df["num_kids"] != 0
    
    # create person types based on the above categories
    df["person_type"] = "na"
    df["person_type"] = np.where(df["child"], "Child", df["person_type"])
    df["person_type"] = np.where(~df["unemployed"] & df["parent"] & ~df["child"], "Working adult with kids", df["person_type"])
    df["person_type"] = np.where(df["unemployed"] & df["parent"] & ~df["child"], "Non-working adult with kids", df["person_type"])
    df["person_type"] = np.where(~df["unemployed"] & ~df["parent"] & ~df["child"], "Working adult without kids", df["person_type"])
    df["person_type"] = np.where(df["unemployed"] & ~df["parent"] & ~df["child"], "Non-working adult without kids", df["person_type"])
    df["person_type"] = np.where(df["senior"] & df["unemployed"], "Retired", df["person_type"])
    df["person_type"] = np.where((~df["child"]) & (df["student"]), "College student", df["person_type"]) # if placed above, everything else overwrites it
    
    # merge some similar gender-categories into one
    df["gender_cleaned"] = df["gender"]
    df["gender_cleaned"] = np.where(df["gender_cleaned"] == "Other/prefer to self-describe", "Other/Prefer to self-describe", df["gender_cleaned"])
    df["gender_cleaned"] = np.where(df["gender_cleaned"] == "Prefer not to answer", "Other/Prefer to self-describe", df["gender_cleaned"])
    df["gender_cleaned"] = np.where(df["gender_cleaned"] == "Non-binary/third gender", "Other/Prefer to self-describe", df["gender_cleaned"])
    df["gender_cleaned"] = np.where(df["gender_cleaned"] == "Transgender", "Other/Prefer to self-describe", df["gender_cleaned"])
    
    # merge some similar income into one
    df["income_cleaned"] = "na"
    df["income_cleaned"] = np.where(df["income_detailed"].isin(["Under $15,000", "$15,000-$24,999"]), "Under $25,000", df['income_cleaned'])
    df["income_cleaned"] = np.where(df["income_detailed"].isin(["$25,000-$34,999", "$35,000-$49,999"]), "$25,000-$49,999", df['income_cleaned'])
    df["income_cleaned"] = np.where(df["income_detailed"].isin(["$50,000-$74,999"]), "$50,000-$74,999", df['income_cleaned'])
    df["income_cleaned"] = np.where(df["income_detailed"].isin(["$75,000-$99,999"]), "$75,000-$99,999", df['income_cleaned'])
    df["income_cleaned"] = np.where(df["income_detailed"].isin(["$100,000-$149,999"]), "$100,000-$149,999", df['income_cleaned'])
    df["income_cleaned"] = np.where(df["income_detailed"].isin(["$150,000-$199,999", "$200,000-$249,999", "$250,000 or more"]), "$150,000 or more", df['income_cleaned'])

def add_terminal_times(df: pd.DataFrame) -> None:
    """
    This function adds terminal times of bike/car trips for each unlinked trip into the main df in-place.
    """
    logging.info("adding terminal times for tazs")

    # read in terminal times
    tazs = gpd.read_file("data/" + handler["taz_terminal_time_file_name"]).dropna(subset=["geometry"]).to_crs("EPSG:4326")

    # create o/d geodataframes from df based on origin/destination latlon
    o_gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["o_lon"], df["o_lat"]), crs="EPSG:4326")
    d_gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["d_lon"], df["d_lat"]), crs="EPSG:4326")

    # by default, terminal times are 0 unless the unlinked trip in the current row starts/ends in a place with terminal time
    df["o_car_terminal_time"] = (
        gpd.sjoin(o_gdf[["geometry"]], tazs[~tazs["TAZ"].isna()], how="left")
        .reset_index()
        .groupby("index")  # after sjoin, can have duplicate rows with multiple mappings for one geometry -- resolve by grouping by index and taking first entry of each
        .first()
        ["TERM_TIME"]
        .fillna(0)  # if no match, there is 0 termianl time
        .values
    )
    df["d_car_terminal_time"] = (
        gpd.sjoin(d_gdf[["geometry"]], tazs[~tazs["TAZ"].isna()], how="left")
        .reset_index()
        .groupby("index")
        .first()
        ["TERM_TIME"]
        .fillna(0)
        .values
    )

    # recalculate adjusted durations based on these car terminal times (and with a bike terminal time of 120 seconds flat)
    df["car_duration_seconds_adj"] = df["car_duration_seconds"] + 60 * df["o_car_terminal_time"] + 60 * df["d_car_terminal_time"]
    df["bike_duration_seconds_adj"] = df["bike_duration_seconds"] + 120
    
def round_off_columns(df: pd.DataFrame) -> None:
    """
    This function rounds off some columns of the dataframe in-place for anonymization.
    """
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
    df["transit_access_dist_mi"] = df["transit_access_dist_mi"].round(2)
    df["transit_egress_dist_mi"] = df["transit_egress_dist_mi"].round(2)
    
# make it so that it only runs once
@st.cache_data()
def prepare_data(df: pd.DataFrame, data_dir: str) -> pd.DataFrame:
    """
    This function is the "main" function for cleaning the raw TBI dataframe.

    Args:
        df (pd.DataFrame): raw TBI df to clean
        data_dir (str): directory of the root TBI OneDrive

    Returns:
        DataFrame: cleaned/fully specified DataFrame
    """
    if handler["cleanup_notebook_path"] is not None:
        logging.info("Running the cleanup notebook")
        
        # check the cleanup notebook is actually ipynb
        if handler["cleanup_notebook_path"].split(".")[-1] != "ipynb":
            logging.exception("Specified cleanup notebook path is not a jupyter notebook")
            raise RuntimeError("Cleanup notebook is not a jupyter notebook")
        
        # convert jupyter notebook to runnable python code
        with open(handler["cleanup_notebook_path"]) as ff:
            nb_in = nbformat.read(ff, nbformat.NO_CONVERT)
        
        # run the python code
        # NOTE: may have to specify the kernel in ExecutePreprocessor arguments
        logging.info("NOTE: this is untested; you may have to manually specify the kernel at line 316 of initialize.py")
        ep = ExecutePreprocessor()
        ep.preprocess(nb_in)
        
        # get the output of the script into df
        df = pd.read_parquet(handler["output_file_name"])
    else:
        logging.info("beginning data intake and cleaning")
        
        # merge in weather
        merge_weather(df)

        # read in rerouting files
        logging.info("reading in rerouting files")
        
        car = pd.read_parquet(data_dir + handler["route_files"][Mode.CAR]).drop("geometry", axis=1, errors="ignore")
        walk = pd.read_parquet(data_dir + handler["route_files"][Mode.WALK]).drop("geometry", axis=1, errors="ignore")
        bike = pd.read_parquet(data_dir + handler["route_files"][Mode.BIKE]).drop("geometry", axis=1, errors="ignore")
        transit = gpd.read_parquet(data_dir + handler["route_files"][Mode.TRANSIT])
        
        # group/cleanup transit
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
        transit_grouped = add_mode_to_column_name(transit_grouped, 'transit')
        
        # merge in rerouted files
        df = df.merge(walk, left_on="trip_id", right_on="walk_trip_id", how="left")
        df = df.merge(bike, left_on="trip_id", right_on="bike_trip_id", how="left")
        df = df.merge(transit_grouped, left_on="trip_id", right_on="transit_trip_id", how="left")
        df = df.merge(car, left_on="trip_id", right_on="car_trip_id", how="left")
        
        # the routes record when you have to leave to catch the bus, not when you want to leave
        # the difference becomes the wait time
        add_transit_wait_time(df)
        
        # merge in estimated transit trip details
        merge_transit_trip_details(df, data_dir)
        
        # add communities to df
        add_CTU(df)

        # clean df mode names
        clean_mode_names(df)

        # do some final column cleanup on df
        final_field_cleanup(df)

        # add terminal time to df
        add_terminal_times(df)

        # round off some columns to df
        round_off_columns(df)
        
        # final miscellaneous things to do before standardization
        
        # apply expansion weights to person trips, vehicle trips, vmt and trips
        df['person_trips'] = df['trip_weight']
        df['vehicle_trips'] = df['vehicle_trips'] * df['trip_weight']
        df['vmt'] = df['vmt'] * df['trip_weight']
        
        # convert to minutes/miles; create na columns
        df["car_distance_miles"] = df["car_distance_meters"] * MILES_PER_METER
        df["car_duration_minutes_adj"] = df["car_duration_seconds_adj"] / 60
        df["car_rerouting_missing"] = df["car_distance_meters"].isna()
        
        df["walk_duration_minutes"] = df["walk_duration_seconds"] / 60
        df["walk_distance_miles"] = df["walk_distance_meters"] * MILES_PER_METER
        df["walk_rerouting_missing"] = df["walk_duration_seconds"].isna()
        
        df["bike_distance_miles"] = df["bike_distance_meters"] * MILES_PER_METER
        df["bike_distance_miles_1"] = df["bike_distance_meters_1"] * MILES_PER_METER
        df["bike_distance_miles_2"] = df["bike_distance_meters_2"] * MILES_PER_METER
        df["bike_distance_miles_3"] = df["bike_distance_meters_3"] * MILES_PER_METER
        df["bike_distance_miles_4"] = df["bike_distance_meters_4"] * MILES_PER_METER
        df["bike_duration_minutes_adj"] = df["bike_duration_seconds_adj"] / 60
        df["bike_rerouting_missing"] = df["bike_distance_meters"].isna()
        
        df["transit_length"] = df["transit_length"] * MILES_PER_METER
        df["transit_access_length"] = df["transit_access_length"] * MILES_PER_METER
        df["transit_rerouting_missing"] = df["transit_duration"].isna()
        
        add_scenarios(df)
    
    return standardize(df)


def process_walk_scenario(scenario_name: str, scenario_df: pd.DataFrame, df: pd.DataFrame):
    """
    This function processes a generic walk scenario that adds a new duration/distance. More specialized functions can be created, but it will need branching in the main
    add_scenarios function and a distinct mapping.

    Args:
        scenario_name (str): the name of the scenario
        scenario_df (pd.DataFrame): the dataframe of the read-in rerouting file
        df (pd.DataFrame): an alias to the overall dataframe
    """
    scenario_df["trip_id"] = scenario_df["trip_id"].astype("str")
    
    # convert to be in line with mapping units
    scenario_df[f"scenario_{scenario_name}_duration_rerouted"] = scenario_df["duration_seconds"] / 60
    scenario_df[f"scenario_{scenario_name}_distance_rerouted"] = scenario_df["distance_meters"] * MILES_PER_METER

    scenario_df = scenario_df.set_index("trip_id").reindex(df["trip_id"].astype(str))
    
    df[f"scenario_{scenario_name}_distance_rerouted"] = scenario_df[f"scenario_{scenario_name}_distance_rerouted"].round().astype("Int32").values
    df[f"scenario_{scenario_name}_duration_rerouted"] = scenario_df[f"scenario_{scenario_name}_duration_rerouted"].round().astype("Int32").values
    df[f"scenario_{scenario_name}_rerouting_missing"] = scenario_df[f"scenario_{scenario_name}_distance_rerouted"].isna().astype("bool").values
    
def process_bike_scenario(scenario_name: str, scenario_df: pd.DataFrame, df: pd.DataFrame):
    """
    This function processes a generic bike scenario that adds a new duration/distance/lts distances. More specialized functions can be created, 
    but it will need branching in the main add_scenarios function and a distinct mapping.

    Args:
        scenario_name (str): the name of the scenario
        scenario_df (pd.DataFrame): the dataframe of the read-in rerouting file
        df (pd.DataFrame): an alias to the overall dataframe
    """
    # convert to be in line with mapping units
    scenario_df[f"scenario_{scenario_name}_duration_rerouted"] = scenario_df["duration_seconds"] / 60
    scenario_df[f"scenario_{scenario_name}_distance_rerouted"] = scenario_df["distance_meters"] * MILES_PER_METER
    scenario_df[f"scenario_{scenario_name}_distance_lts_1_rerouted"] = scenario_df["distance_meters_1"] * MILES_PER_METER
    scenario_df[f"scenario_{scenario_name}_distance_lts_2_rerouted"] = scenario_df["distance_meters_2"] * MILES_PER_METER
    scenario_df[f"scenario_{scenario_name}_distance_lts_3_rerouted"] = scenario_df["distance_meters_3"] * MILES_PER_METER
    scenario_df[f"scenario_{scenario_name}_distance_lts_4_rerouted"] = scenario_df["distance_meters_4"] * MILES_PER_METER
    
    scenario_df = scenario_df.set_index("trip_id").reindex(df["trip_id"].astype(str))
    
    df[f"scenario_{scenario_name}_distance_rerouted"] = scenario_df[f"scenario_{scenario_name}_distance_rerouted"].round().astype("Int32").values
    df[f"scenario_{scenario_name}_duration_rerouted"] = scenario_df[f"scenario_{scenario_name}_duration_rerouted"].round().astype("Int32").values
    
    df[f"scenario_{scenario_name}_distance_lts_1_rerouted"] = scenario_df[f"scenario_{scenario_name}_distance_lts_1_rerouted"].round().astype("Int32").values
    df[f"scenario_{scenario_name}_distance_lts_2_rerouted"] = scenario_df[f"scenario_{scenario_name}_distance_lts_2_rerouted"].round().astype("Int32").values
    df[f"scenario_{scenario_name}_distance_lts_3_rerouted"] = scenario_df[f"scenario_{scenario_name}_distance_lts_3_rerouted"].round().astype("Int32").values
    df[f"scenario_{scenario_name}_distance_lts_4_rerouted"] = scenario_df[f"scenario_{scenario_name}_distance_lts_4_rerouted"].round().astype("Int32").values
    
    df[f"scenario_{scenario_name}_rerouting_missing"] = scenario_df[f"scenario_{scenario_name}_distance_rerouted"].isna().astype("bool").values
    
def process_transit_scenario(scenario_name: str, scenario_df: pd.DataFrame, df: pd.DataFrame):
    """
    This function processes a generic transit scenario that adds a new duration/distance/transit details. More specialized functions can be created, 
    but it will need branching in the main add_scenarios function and a distinct mapping.
    This function utilizes the transit_cleanup function defined previously to do trip grouping.

    Args:
        scenario_name (str): the name of the scenario
        scenario_df (pd.DataFrame): the dataframe of the read-in rerouting file
        df (pd.DataFrame): an alias to the overall dataframe
    """
    scenario_df = transit_cleanup(scenario_df)
    
    scenario_df[f"scenario_{scenario_name}_distance_rerouted"] = scenario_df["length"] * MILES_PER_METER
    scenario_df[f"scenario_{scenario_name}_access_length_rerouted"] = scenario_df["access_length"] * MILES_PER_METER
    scenario_df[f"scenario_{scenario_name}_duration_rerouted"] = scenario_df["duration"]
    scenario_df[f"scenario_{scenario_name}_num_transfers_rerouted"] = scenario_df["num_transfers"] 
    scenario_df[f"scenario_{scenario_name}_nontransit_duration"] = scenario_df["non_transit_duration"]
    
    scenario_df = scenario_df.set_index("trip_id").reindex(df["trip_id"].astype(str))
    
    df[f"scenario_{scenario_name}_distance_rerouted"] = scenario_df[f"scenario_{scenario_name}_distance_rerouted"].round().astype("Int16").values
    df[f"scenario_{scenario_name}_duration_rerouted"] = scenario_df[f"scenario_{scenario_name}_duration_rerouted"].round().astype("Int16").values
    df[f"scenario_{scenario_name}_access_length_rerouted"] = scenario_df[f"scenario_{scenario_name}_access_length_rerouted"].round().astype("Int16").values
    df[f"scenario_{scenario_name}_num_transfers_rerouted"] = scenario_df[f"scenario_{scenario_name}_num_transfers_rerouted"].astype("Int8").values
    df[f"scenario_{scenario_name}_num_transfers_rerouted"] = scenario_df[f"scenario_{scenario_name}_num_transfers_rerouted"].astype("Int8").values
    df[f"scenario_{scenario_name}_rerouting_missing"] = scenario_df[f"scenario_{scenario_name}_distance_rerouted"].isna().astype("bool").values
    
def process_car_scenario(scenario_name: str, scenario_df: pd.DataFrame, df: pd.DataFrame):
    scenario_df[f"scenario_{scenario_name}_duration_rerouted"] = scenario_df["duration_seconds"] / 60
    scenario_df[f"scenario_{scenario_name}_distance_rerouted"] = scenario_df["distance_meters"] * MILES_PER_METER
    
    df[f"scenario_{scenario_name}_duration_rerouted"] = df.apply(
        lambda x: get_car_data(x, f"scenario_{scenario_name}_duration_rerouted", scenario_df), axis=1
    ).round().astype("Int16").values
    
    df[f"scenario_{scenario_name}_distance_rerouted"] = df.apply(
        lambda x: get_car_data(x, f"scenario_{scenario_name}_distance_rerouted", scenario_df), axis=1
    ).round().astype("Int16").values

def add_scenarios(df: pd.DataFrame):
    logging.info("Adding scenarios to the dataframe")
    # get rid of all existing scenario columns
    for column in df.columns:
        if "scenario" in column:
            df.drop(columns=[column], inplace=True)
    
    # iterate over all scenarios
    for mode in handler["scenarios"]:
        for scenario, info in handler["scenarios"][mode].items():
            # don't process default sceanrios
            if scenario == "default":
                continue
            
            logging.info(f"Reading in scenario {scenario} for mode {mode}")
            
            # try to read in the scenario file
            try:
                lib = pd
                if mode == "transit":
                    lib = gpd
                    
                if info["file_path"].split(".")[-1] == "parquet":
                    scenario_df = lib.read_parquet(dir + info["file_path"])
                elif info["file_path"].split(".")[-1] == "csv":
                    scenario_df = lib.read_csv(dir + info["file_path"])
                scenario_df.drop(["geometry"], axis=1, errors="ignore")
            except Exception:
                logging.exception(f"Error reading in scenario file for scenario {scenario} for mode {mode}")
                raise RuntimeError("There was an issue reading in a scenario file")
            
            # do the corresponding process function to add it into the df according to a well-specified naming scheme
            if mode == Mode.BIKE:
                process_bike_scenario(scenario, scenario_df, df)
            elif mode == Mode.WALK:
                process_walk_scenario(scenario, scenario_df, df)
            elif mode == Mode.TRANSIT:
                process_transit_scenario(scenario, scenario_df, df)
            elif mode == Mode.CAR:
                process_car_scenario(scenario, scenario_df, df)
            else:
                raise RuntimeError("Something went wrong with the mode enum")
            

# metaprocessing to make things easier: (generally shouldn't edit)

def standardize(df: pd.DataFrame) -> pd.DataFrame:
    """This function standardizes the final cleaned up dataframe in terms of column naming/columns and throws and error if any required columns are missing

    Args:
        df (pd.DataFrame): The final cleaned dataframe

    Raises:
        RuntimeError: Occurs if a required input column is not present
    """
    logging.info("Standardizing the cleaned df for input/saving to disk")
    # invert mappings to get input column -> standardized column
    mappings = {value: key for key, value in handler["mappings"].items()}
    
    df = df.reset_index()
    # df.to_csv("data/temp2.csv")
    # go through and rename all columns described in the mapping
    for column in df.columns:
        if column in mappings:
            df = df.rename(columns={column: mappings[column]})
    
    # check all necessary columns are within it
    for column in mappings.values():
        if column not in df.columns:
            logging.exception("Cannot proceed -- the dataframe created in initialize.py does not have all the required inputs or the mappings described in config.yml are wrong")
            raise RuntimeError(f"The cleaned dataframe does not contain all required columns -- {column}")
    
    # TODO: can assert more invariants here for more accurate standardization
    
    logging.info("exporting newly created table to csv")
    df.to_csv(handler["output_file_name"] + ".csv", index=False)
    
    # do anonymization in parallel and save that to csv
    anonymize(df)
    
    return df

def anonymize(df: pd.DataFrame):
    """This function creates an anonymized and compressed parquet version of the main cleaned dataframe. 

    Args:
        df (pd.DataFrame): The cleaned, standardized dataframe
    """
    logging.info("Running anonymization of data")
    # only keep important columns (specified in config somewhere, whether as scenario or as a base thing)
    df_anonymous = df[[col for col in df.columns if (col in handler["mappings"].keys() or "scenario" in col)]].copy()
    
    # anonymize person id and trip id
    df_anonymous["person_id"] = pd.factorize(df["person_id"])[0]
    df_anonymous["person_id"] = df_anonymous["person_id"].astype("Int32")
    
    trips = list(itertools.chain(*df["trip_id"].apply(lambda x: literal_eval(str(x))).values))
    temp = pd.factorize(trips)
    trip_conversion = dict(zip(temp[1], temp[0]))
    
    def map_trip_ids(x: list) -> list:
        res = list(map(lambda ele: trip_conversion[ele], x))
        return res

    df_anonymous["trip_id"] = df["trip_id"].apply(lambda x: literal_eval(x)).apply(lambda x: map_trip_ids(x))
    
    # TODO: with minutes, we can compress to int16 proabbly
    
    # compress datatypes + renaming
    df_anonymous["wave"] = df["wave"].astype("Int8")
    # df_anonymous["person_id"] = df_anonymous["person_id"].astype("Int32")
    df_anonymous["duration"] = df["duration"].round().astype("Int16")
    df_anonymous["distance"] = df["distance"].round(1).astype("Float32")
    df_anonymous["vehicle_trips"] = df["vehicle_trips"].astype("Float32")
    df_anonymous["vmt"] = df["vmt"].astype("Float32")
    df_anonymous["temperature"] = df["temperature"].astype("Float32")
    df_anonymous["precipitation"] = df["precipitation"].astype("Float32")
    df_anonymous["snow_depth"] = df["snow_depth"].astype("Float32")
    
    df_anonymous["car_distance_rerouted"] = df["car_distance_rerouted"].round().astype("Int32")
    df_anonymous["car_duration_rerouted"] = df["car_duration_rerouted"].round(1).astype("Float32")
    df_anonymous["car_rerouting_missing"] = df["car_rerouting_missing"].astype("bool")
    
    df_anonymous["walk_duration_rerouted"] = df["walk_duration_rerouted"].round().astype("Int32")
    df_anonymous["walk_distance_rerouted"] = df["walk_distance_rerouted"].round().astype("Int32")
    df_anonymous["walk_rerouting_missing"] = df["walk_rerouting_missing"].astype("bool")
    
    df_anonymous["bike_distance_rerouted"] = df["bike_distance_rerouted"].round().astype("Int32")
    df_anonymous["bike_distance_lts_1_rerouted"] = df["bike_distance_lts_1_rerouted"].round().astype("Int32")
    df_anonymous["bike_distance_lts_2_rerouted"] = df["bike_distance_lts_2_rerouted"].round().astype("Int32")
    df_anonymous["bike_distance_lts_3_rerouted"] = df["bike_distance_lts_3_rerouted"].round().astype("Int32")
    df_anonymous["bike_distance_lts_4_rerouted"] = df["bike_distance_lts_4_rerouted"].round().astype("Int32")
    df_anonymous["bike_duration_rerouted"] = df["bike_duration_rerouted"].round(1).astype("Float32")
    df_anonymous["bike_rerouting_missing"] = df["bike_rerouting_missing"].astype("bool")
    
    df_anonymous["transit_duration_rerouted"] = df["transit_duration_rerouted"].round().astype("Int16")
    df_anonymous["transit_rerouting_missing"] = df["transit_rerouting_missing"].round().astype("bool")
    df_anonymous["transit_access_length_rerouted"] = df["transit_access_length_rerouted"].round().astype("Int16")
    df_anonymous["transit_num_transfers_rerouted"] = df["transit_num_transfers_rerouted"].round().astype("Int8")
    df_anonymous["transit_access_length"] = df["transit_access_length"].round().astype("Int16")
    df_anonymous["transit_num_transfers"] = df["transit_num_transfers"].round().astype("Int8")
    
    df_anonymous["trip_id"] = df_anonymous["trip_id"].astype(str).str.replace("  ", ", ")
    
    
    df_anonymous.to_parquet(handler["output_file_name"] + ".parquet")
    
    return 0
