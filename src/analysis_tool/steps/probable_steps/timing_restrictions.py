import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import inspect

from steps.parent_classes import CategoricalStep
from steps.enums import *
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
        return df.groupby(["wave", "person_id", "travel_date"]).apply(lambda x: evaluate_likely_timing(len(x), list(x["depart_time"]), x["duration"].values, x[alt_mode_times].values))

def evaluate_likely_timing(chunk_len: int, depart_time: list[str], leg_durations: np.ndarray[float], alt_durations: np.ndarray[float]):
    # if there is only an inbound and outbound trip, don't need to worry about timing
    if chunk_len == 2:
        return True
    leg_starts = np.fromiter(map(convert_to_minutes, depart_time), dtype=np.float32)
    ref = leg_starts[0]
    # start times, starting by 0 and accounting for midnight wraparound with the mod function, for each leg of the complete tour
    leg_starts = (leg_starts - ref) % 1440
    # calculate end times relative to the start times using the duration category
    leg_ends = leg_starts + leg_durations
    
    # alternative durations for each of the legs
    # if any invalid durations, means routing wasn't possible (generally only for transit)
    # return true since this isn't due to timing issues
    if -1 in alt_durations:
        return True

    for i in range(1, chunk_len - 1):
        # for probable, consider ALL adjacent trips; not just adjacent trips that are fixed
        # if you would need to start before the last trip finished, not feasible
        if leg_ends[i] - alt_durations[i] < leg_starts[i]: 
            return False
        # if you would arrive after the next trip began, not feasible
        if leg_starts[i] + alt_durations[i] > leg_ends[i]: 
            return False

    # feasible if nothing is weird
    return True

class WalkTimingStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df, "likely_walk_timing", Mode.WALK, Phase.PROBABLE)
        
        self.df.loc[:, "walk_duration"] = self.df["walk_duration_seconds"] / 60
        probable_walking = evaluate_timing(df, "walk_duration")
        probable_walking = probable_walking.reset_index().rename(columns={0: self.name})
        
        temp = df[["wave", "person_id", "travel_date"]].copy()
        temp = temp.reset_index().merge(probable_walking, on=["wave", "person_id", "travel_date"], how="left").set_index("index")
        
        df[self.name] = temp[self.name]
        
    def get_summary_statistics(self):
        return show_value_counts(self.df, [[x, self.name] for x in [self.mode, Mode.CAR]])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Whether a trip had a likely walk timing\nfor canonical walk trips")
        ax[1].set_title("Whether a trip had a likely walk timing\nfor canonical car trips")
        
        return fig, ax
    
    def apply_step(self) -> None:
        super().apply_step(~self.df[self.name])
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""As discussed in the feasibility analysis, a trip was considered feasible timing-wise if the actor could work around all discretionary trips (possibly skipping them and doing them another time) to manage to reach all non-negotiable, non-discretionary trips. However, it is not necessarily the case that the actor would be more likely to embark on a trip if they needed to abandon some of their daily activities like shopping or social visits. 

        As an example, consider a daily activity pattern consisting of going from home to work, from work to shop, and finally, from shopping back to home. A feasible trip would allow the shoppign trip to be skipped (put off for another time), while a more likely trip would facilitate going on the shopping trip still.

        Therefore, we consider a trip most likely to switch if, even with the duration increases that come with switching to non-car modes, the daily acitivies can still be done without any overlaps/need to skip any of them to make to the next.""")
        
        # summary figure
        res.append("""Placeholder""")
        
        # summary statistics
        res.append("Placeholder")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
        
        
class BikeTimingStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df, "likely_bike_timing", Mode.BIKE, Phase.PROBABLE)
        
        self.df.loc[:, "bike_duration"] = self.df["bike_duration_seconds_adj"] / 60
        probable_biking = evaluate_timing(df, "bike_duration")
        probable_biking = probable_biking.reset_index().rename(columns={0: self.name})
        
        temp = df[["wave", "person_id", "travel_date"]].copy()
        temp = temp.reset_index().merge(probable_biking, on=["wave", "person_id", "travel_date"], how="left").set_index("index")
        
        df[self.name] = temp[self.name]
        
    def get_summary_statistics(self):
        return show_value_counts(self.df, [[x, self.name] for x in [self.mode, Mode.CAR]])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Whether a trip had a likely bike timing\nfor canonical bike trips")
        ax[1].set_title("Whether a trip had a likely bike timing\nfor canonical car trips")
        
        return fig, ax
    
    def apply_step(self) -> None:
        super().apply_step(~self.df[self.name])
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""As discussed in the feasibility analysis, a trip was considered feasible timing-wise if the actor could work around all discretionary trips (possibly skipping them and doing them another time) to manage to reach all non-negotiable, non-discretionary trips. However, it is not necessarily the case that the actor would be more likely to embark on a trip if they needed to abandon some of their daily activities like shopping or social visits. 

        As an example, consider a daily activity pattern consisting of going from home to work, from work to shop, and finally, from shopping back to home. A feasible trip would allow the shoppign trip to be skipped (put off for another time), while a more likely trip would facilitate going on the shopping trip still.

        Therefore, we consider a trip most likely to switch if, even with the duration increases that come with switching to non-car modes, the daily acitivies can still be done without any overlaps/need to skip any of them to make to the next.""")
        
        # summary figure
        res.append("""Placeholder""")
        
        # summary statistics
        res.append("Placeholder")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
        
        
class TransitTimingStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df, "likely_transit_timing", Mode.TRANSIT, Phase.PROBABLE)
        
        probable_transit = evaluate_timing(df, "transit_duration")
        probable_transit = probable_transit.reset_index().rename(columns={0: self.name})
        
        temp = df[["wave", "person_id", "travel_date"]].copy()
        temp = temp.reset_index().merge(probable_transit, on=["wave", "person_id", "travel_date"], how="left").set_index("index")
        
        df[self.name] = temp[self.name]
        
    def get_summary_statistics(self):
        return show_value_counts(self.df, [[x, self.name] for x in [self.mode, Mode.CAR]])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Whether a trip had a likely transit timing\nfor canonical transit trips")
        ax[1].set_title("Whether a trip had a likely transit timing\nfor canonical car trips")
        
        return fig, ax
    
    def apply_step(self) -> None:
        super().apply_step(~self.df[self.name])
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""As discussed in the feasibility analysis, a trip was considered feasible timing-wise if the actor could work around all discretionary trips (possibly skipping them and doing them another time) to manage to reach all non-negotiable, non-discretionary trips. However, it is not necessarily the case that the actor would be more likely to embark on a trip if they needed to abandon some of their daily activities like shopping or social visits. 

        As an example, consider a daily activity pattern consisting of going from home to work, from work to shop, and finally, from shopping back to home. A feasible trip would allow the shoppign trip to be skipped (put off for another time), while a more likely trip would facilitate going on the shopping trip still.

        Therefore, we consider a trip most likely to switch if, even with the duration increases that come with switching to non-car modes, the daily acitivies can still be done without any overlaps/need to skip any of them to make to the next.""")
        
        # summary figure
        res.append("""Placeholder""")
        
        # summary statistics
        res.append("Placeholder")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
        
    
        
        
        
        
        