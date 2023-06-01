import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import inspect

from steps.parent_classes import CategoricalStep, Mode
from steps.figure_lib import *

import sys
sys.path.append("...")
from settings import handler

fixed_purposes = handler["fixed_purposes"]

def convert_to_minutes(str):
    hours, minutes, seconds = [int(x) for x in str.split(":")]
    return hours * 60 + minutes + seconds / 60

def evaluate_timing(df, alt_mode_times):
    with st.spinner("Running the timing logic..."):
        return df.groupby(["wave", "person_id", "travel_date"]).apply(lambda x: evaluate_feasible_timing(x, alt_mode_times))

def evaluate_feasible_timing(chunk, alt_mode_times: str):
    # if there is only an inbound and outbound trip, don't need to worry about timing
    if len(chunk) == 2:
        return True
    leg_starts = chunk["depart_time"].apply(lambda x: convert_to_minutes(x)).values
    ref = leg_starts[0]
    # start times, starting by 0 and accounting for midnight wraparound with the mod function, for each leg of the complete tour
    leg_starts = [(x - ref) % 1440 for x in chunk["depart_time"].apply(lambda x: convert_to_minutes(x)).values]
    leg_durations = chunk["duration"].values
    # calculate end times relative to the start times using the duration category
    leg_ends = [(x + y) for (x, y) in zip(leg_starts, leg_durations)]
    # these are arrays indicating whether each leg of the complete tour is a fixed arrival/departure
    fixed_arrivals = chunk["d_purpose_category"].isin(fixed_purposes).values
    fixed_departures = chunk["o_purpose_category"].isin(fixed_purposes).values
    
    # sanity check; if the atlernative time for any of the legs can't be found, return False (means can't route it feasibly, usually for transit)
    # do this as preprocessing
    # if ~(chunk["trip_id"].isin(alt_mode_times.index).any()):
    #     return False
    # alternative durations for each of the legs
    alt_durations = chunk[alt_mode_times].values # make it a col in the dataframe to simplify things
    # if any invalid durations, means routing wasn't possible (generally only for transit)
    # return true since this isn't due to timing issues
    if -1 in alt_durations:
        return True
    
    # return true if there aren't any fixed things to work around
    # also return true if there is only one fixed thing--all trips of these kind can be boiled down to traveling to the fixed thing and traveling back if all non-fixed, discretionary trips are omitted; which can be scheduled around feasibly
    if fixed_arrivals.sum() <= 1:
        return True
    
    # keeps track of a previous fixed arrival trip to compare against a current one (see whether they overlap)
    prev_fixed_arrival = -1
    for i in range(len(chunk)):
        if fixed_arrivals[i]: # if current trip is fixed arrival
            if prev_fixed_arrival != -1: # if there exists some previous fixed arrival trip
                if leg_ends[i] - alt_durations[i] < leg_ends[prev_fixed_arrival]: # if there is an overlap between this trip and the pregvious fixed arrival trip, not feasible
                    return False
            prev_fixed_arrival = i # update previous fixed arrival trip
            
    # basically the same as the above, except work backwards since we want to consider whether the next trip would overlap
    next_fixed_departure = -1
    for i in range(len(chunk)-1, -1, -1):
        if fixed_departures[i]:
            if next_fixed_departure != -1:
                if leg_starts[i] + alt_durations[i] > leg_starts[next_fixed_departure]:
                    return False
                next_fixed_departure = i

    # feasible if nothing is weird
    return True

class WalkTimingStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df, "feasible_walk_timing", Mode.WALK)
        
        self.df.loc[:, "walk_duration"] = self.df["walk_duration_seconds"] / 60
        feasible_walking = evaluate_timing(df, "walk_duration")
        feasible_walking = feasible_walking.reset_index().rename(columns={0: self.name})
        
        temp = df[["wave", "person_id", "travel_date"]].copy()
        temp = temp.merge(feasible_walking, on=["wave", "person_id", "travel_date"], how="left")
        
        df[self.name] = temp[self.name]
        
    def get_summary_statistics(self):
        return show_value_counts(self.df, [[x, self.name] for x in [self.mode, Mode.CAR]])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Whether a trip had a feasible walk timing\nfor canonical walk trips")
        ax[1].set_title("Whether a trip had a feasible walk timing\nfor canonical car trips")
        
        return fig, ax
    
    def apply_step(self) -> None:
        super().apply_step(~self.df[self.name])
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""For some people, it is infeasible to switch from a car mode to an alternative mode due to timing constraints; with the longer durations of alternative modes, a person may not have the ability to do everything they need to in a given day.

        Here, trips are feasible with respect to timing if it is possible to fit in all the fixed trips of a day (which have purposes related to work or school), even if the more discretionary, non-fixed trips of a day (e.g., shopping, social visits) may have to be rescheduled or cancelled. """)
        
        # summary figure
        res.append("""Here, a bar plot of the result of the timing logic when applied to walk shifts can be seen.""")
        
        # summary statistics
        res.append("Here, the value counts of the result of the timing logic when applied to walk shifts can be seen.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
        
        
class TransitTimingStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df, "feasible_transit_timing", Mode.TRANSIT)
        
        self.df.loc[:, "transit_duration"] = self.df["transit_duration"].fillna(-1)
        feasible_transit = evaluate_timing(df, "transit_duration")
        feasible_transit = feasible_transit.reset_index().rename(columns={0: self.name})
        
        temp = df[["wave", "person_id", "travel_date"]].copy()
        temp = temp.merge(feasible_transit, on=["wave", "person_id", "travel_date"], how="left")
        
        df[self.name] = temp[self.name]
        
    def get_summary_statistics(self):
        return show_value_counts(self.df, [[x, self.name] for x in [self.mode, Mode.CAR]])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Whether a trip had a feasible transit timing\nfor canonical transit trips")
        ax[1].set_title("Whether a trip had a feasible transit timing\nfor canonical car trips")
        
        return fig, ax
    
    def apply_step(self) -> None:
        super().apply_step(~self.df[self.name])
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""For some people, it is infeasible to switch from a car mode to an alternative mode due to timing constraints; with the longer durations of alternative modes, a person may not have the ability to do everything they need to in a given day.

        Here, trips are feasible with respect to timing if it is possible to fit in all the fixed trips of a day (which have purposes related to work or school), even if the more discretionary, non-fixed trips of a day (e.g., shopping, social visits) may have to be rescheduled or cancelled. """)
        
        # summary figure
        res.append("""Here, a bar plot of the result of the timing logic when applied to transit shifts can be seen.""")
        
        # summary statistics
        res.append("Here, the value counts of the result of the timing logic when applied to transit shifts can be seen.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
        
        
class BikeTimingStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df, "feasible_bike_timing", Mode.BIKE)
        
        self.df.loc[:, "bike_duration"] = self.df["bike_weight"] / 60
        feasible_biking = evaluate_timing(df, "bike_duration")
        feasible_biking = feasible_biking.reset_index().rename(columns={0: self.name})
        
        temp = df[["wave", "person_id", "travel_date"]].copy()
        temp = temp.merge(feasible_biking, on=["wave", "person_id", "travel_date"], how="left")
        
        df[self.name] = temp[self.name]
        
    def get_summary_statistics(self):
        return show_value_counts(self.df, [[x, self.name] for x in [self.mode, Mode.CAR]])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Whether a trip had a feasible bike timing\nfor canonical walk trips")
        ax[1].set_title("Whether a trip had a feasible bike timing\nfor canonical car trips")
        
        return fig, ax
    
    def apply_step(self) -> None:
        super().apply_step(~self.df[self.name])
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""For some people, it is infeasible to switch from a car mode to an alternative mode due to timing constraints; with the longer durations of alternative modes, a person may not have the ability to do everything they need to in a given day.

        Here, trips are feasible with respect to timing if it is possible to fit in all the fixed trips of a day (which have purposes related to work or school), even if the more discretionary, non-fixed trips of a day (e.g., shopping, social visits) may have to be rescheduled or cancelled. """)
        
        # summary figure
        res.append("""Here, a bar plot of the result of the timing logic when applied to bike shifts can be seen.""")
        
        # summary statistics
        res.append("Here, the value counts of the result of the timing logic when applied to bike shifts can be seen.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
        
    
        
        
        
        
        