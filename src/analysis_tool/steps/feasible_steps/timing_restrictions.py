import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import inspect

from steps.parent_classes import *
from steps.figure_lib import *

import sys
sys.path.append("...")
from settings import handler

fixed_purposes = set(handler["fixed_purposes"])

def is_in_set(a, b):
    return [x in b for x in a]

def over_cutoff(x, cutoff: int):
    sum = 0
    for ele in x:
        sum += ele
        if sum > cutoff:
            return True
        
    return False

def convert_to_minutes(temp: str) -> float:
    return int(temp[0:2]) * 60 + int(temp[3:5]) + int(temp[6:8]) / 60

def evaluate_timing(df: pd.DataFrame, alt_mode_times: str):
    with st.spinner("Running timing logic"):
        return df.groupby(["wave", "person_id", "travel_date"]).apply(lambda x: evaluate_feasible_timing(len(x), list(x["depart_time"]), x["duration"].values, list(x["d_purpose_category"]), list(x["o_purpose_category"]), x[alt_mode_times].values))

def evaluate_feasible_timing(chunk_len: int, depart_time: list[str], leg_durations: 'np.ndarray[float]', d_purpose: list[str], o_purpose: list[str], alt_durations: list[float]):
    # if there is only an inbound and outbound trip, don't need to worry about timing
    if chunk_len == 2:
        return True
    leg_starts = np.fromiter(map(convert_to_minutes, depart_time), dtype=np.float32)
    ref = leg_starts[0]
    # start times, starting by 0 and accounting for midnight wraparound with the mod function, for each leg of the complete tour
    leg_starts = (leg_starts - ref) % 1440
    # calculate end times relative to the start times using the duration category
    leg_ends = leg_starts + leg_durations
    # these are arrays indicating whether each leg of the complete tour is a fixed arrival/departure
    fixed_arrivals = is_in_set(d_purpose, fixed_purposes)
    fixed_departures = is_in_set(o_purpose, fixed_purposes)
            
    # if the trip takes longer than 24 hours (usually because transit is not available), the timing is not feasible
    if alt_durations.any() > 1440:
        return False
    
    # sanity check; if the atlernative time for any of the legs can't be found, return False (means can't route it feasibly, usually for transit)
    # do this as preprocessing
    # if ~(chunk["trip_id"].isin(alt_mode_times.index).any()):
    #     return False
    # alternative durations for each of the legs
    # if any invalid durations, means routing wasn't possible (generally only for transit)
    # return true since this isn't due to timing issues
    if -1 in alt_durations:
        return True
    # return true if there aren't any fixed things to work around
    # also return true if there is only one fixed thing--all trips of these kind can be boiled down to traveling to the fixed thing and traveling back if all non-fixed, discretionary trips are omitted; which can be scheduled around feasibly
    if not over_cutoff(fixed_arrivals, 1):
        return True

    alt_durations_cumul = np.cumsum(alt_durations)
    
    # keeps track of a previous fixed arrival trip to compare against a current one (see whether they overlap)
    prev_fixed_arrival = -1
    for i in range(chunk_len):
        if fixed_arrivals[i]: # if current trip is fixed arrival
            if prev_fixed_arrival != -1: # if there exists some previous fixed arrival trip
                if leg_ends[i] - (alt_durations_cumul[i] - alt_durations_cumul[prev_fixed_arrival]) < leg_starts[prev_fixed_arrival + 1]: # if there is an overlap between this trip and the pregvious fixed arrival trip, not feasible
                    return False
            prev_fixed_arrival = i # update previous fixed arrival trip
    # basically the same as the above, except work backwards since we want to consider whether the next trip would overlap
    next_fixed_departure = -1
    for i in range(chunk_len - 1, -1, -1):
        if fixed_departures[i]:
            if next_fixed_departure != -1:
                if leg_starts[i] + (alt_durations_cumul[next_fixed_departure] - alt_durations_cumul[i]) > leg_ends[next_fixed_departure - 1]:
                    return False
                next_fixed_departure = i

    # feasible if nothing is weird
    return True

class WalkTimingStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame, column="walk_duration_seconds", scenario=False):
        super().__init__(df, "feasible_walk_timing", Mode.WALK, Phase.FEASIBLE)
        
        # make the name distinct if we are at a scenario
        if scenario:
            self.name = self.name + "_scenario_" + column
        
        if column == "walk_duration_seconds":
            self.df.loc[:, "walk_duration"] = self.df[column] / 60
            feasible_walking = evaluate_timing(df, "walk_duration")
        else:
            feasible_walking = evaluate_timing(df, column)
            
        feasible_walking = feasible_walking.reset_index().rename(columns={0: self.name})
        
        temp = df[["wave", "person_id", "travel_date"]].copy()
        temp = temp.reset_index().merge(feasible_walking, on=["wave", "person_id", "travel_date"], how="left").set_index("index")
        
        df[self.name] = temp[self.name]
        
    def get_summary_statistics(self):
        return show_value_counts(self.df, [[x, self.name] for x in [self.mode, Mode.CAR]])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Whether a trip had a feasible walk timing\nfor observed walk trips")
        ax[1].set_title("Whether a trip had a feasible walk timing\nfor observed car trips")
        
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
    
    def __init__(self, df: pd.DataFrame, column="transit_duration", scenario=False):
        super().__init__(df, "feasible_transit_timing", Mode.TRANSIT, Phase.FEASIBLE)
        
        # make the name distinct if we are at a scenario
        if scenario:
            self.name = self.name + "_scenario_" + column
        
        if column == "transit_duration":
            self.df.loc[:, column] = self.df[column].fillna(9999999)  # if there is no path, it's not feasible
            feasible_transit = evaluate_timing(df, column)
        else:
            feasible_transit = evaluate_timing(df, column)
        feasible_transit = feasible_transit.reset_index().rename(columns={0: self.name})
        
        temp = df[["wave", "person_id", "travel_date"]].copy()
        temp = temp.reset_index().merge(feasible_transit, on=["wave", "person_id", "travel_date"], how="left").set_index("index")
        
        df[self.name] = temp[self.name]
        
    def get_summary_statistics(self):
        return show_value_counts(self.df, [[x, self.name] for x in [self.mode, Mode.CAR]])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Whether a trip had a feasible transit timing\nfor observed transit trips")
        ax[1].set_title("Whether a trip had a feasible transit timing\nfor observed car trips")
        
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
    
    def __init__(self, df: pd.DataFrame, column="bike_duration_seconds_adj", scenario=False):
        super().__init__(df, "feasible_bike_timing", Mode.BIKE, Phase.FEASIBLE)
        
        # make the name distinct if we are at a scenario
        if scenario:
            self.name = self.name + "_scenario_" + column
        
        if column == "bike_duration_seconds_adj":
            self.df.loc[:, "bike_duration"] = self.df[column] / 60
            feasible_biking = evaluate_timing(df, "bike_duration")
        else:
            feasible_biking = evaluate_timing(df, column)
            
        feasible_biking = feasible_biking.reset_index().rename(columns={0: self.name})
        
        temp = df[["wave", "person_id", "travel_date"]].copy()
        temp = temp.reset_index().merge(feasible_biking, on=["wave", "person_id", "travel_date"], how="left").set_index("index")
        
        df[self.name] = temp[self.name]
        
    def get_summary_statistics(self):
        return show_value_counts(self.df, [[x, self.name] for x in [self.mode, Mode.CAR]])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Whether a trip had a feasible bike timing\nfor observed walk trips")
        ax[1].set_title("Whether a trip had a feasible bike timing\nfor observed car trips")
        
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
    
        
    
        
        
        
        
        