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


def calculate_available_time(df: pd.DataFrame): 
    '''
    Determines the available time in minutes without conflicting with an adjacent
    required activity.  Allow up to 5 minutes early/late.  Returns a series
    of the available times in minutes
    '''

    df['depart_time_dt'] = pd.to_datetime(df['depart_time'], format="%H:%M:%S")
    df['arrive_time_dt'] = pd.to_datetime(df['arrive_time'], format="%H:%M:%S")

    # only constrain mandatory activies
    #df['fixed_depart'] = df['o_purpose_category'].apply(lambda x : x in ['Work', 'School', 'Escort'])
    #df['fixed_arrive'] = df['d_purpose_category'].apply(lambda x : x in ['Work', 'School', 'Escort'])
    df['fixed_depart'] = df['o_purpose_category'].apply(lambda x : x != 'Home')
    df['fixed_arrive'] = df['d_purpose_category'].apply(lambda x : x != 'Home')

    # calculate when I need to be there next    
    df = df.sort_values(['wave','person_id','travel_date','trip_id'])
    df['fixed_depart_time'] = pd.to_datetime(np.where(df['fixed_depart'], df['depart_time'], None), format="%H:%M:%S")
    df['fixed_arrive_time'] = pd.to_datetime(np.where(df['fixed_arrive'], df['arrive_time'], None), format="%H:%M:%S")
    df['fixed_depart_time'] = df.groupby(['wave','person_id','travel_date'])['fixed_depart_time'].ffill()
    df['fixed_arrive_time'] = df.groupby(['wave','person_id','travel_date'])['fixed_arrive_time'].bfill()

    # allow people to be 5 minutes late and leave 5 minutes early
    df['available_time'] = (df['fixed_arrive_time'] - df['fixed_depart_time']).apply(lambda x : x.seconds / 60 + 5 + 5)
    
    # missing values are unconstrained
    df['available_time'] = df['available_time'].fillna(1440) 
    
    return df['available_time']


class WalkTimingStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame, column="walk_duration_seconds", scenario=False):
        super().__init__(df, "feasible_walk_timing", Mode.WALK, Phase.FEASIBLE)
        
        df['available_time'] = calculate_available_time(df)
        
        if column == "walk_duration_seconds":
            self.df.loc[:, "walk_duration"] = self.df[column] / 60
            df[self.name] = (df["walk_duration"] <= df['available_time'])
        else:
            df[self.name] = (df[column] <= df['available_time'])
            
     
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
                
        df['available_time'] = calculate_available_time(df)
        
        if column == "transit_duration":
            self.df.loc[:, column] = self.df[column].fillna(9999999)  # if there is no path, it's not feasible
            df[self.name] = (df["transit_duration"] <= df['available_time'])
        else:
            df[self.name] = (df[column] <= df['available_time'])
            
        
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
                
        df['available_time'] = calculate_available_time(df)
        
        if column == "bike_duration_seconds_adj":
            self.df.loc[:, "bike_duration"] = self.df[column] / 60
            df[self.name] = (df["bike_duration"] <= df['available_time'])
        else:
            df[self.name] = (df[column] <= df['available_time'])
            
        
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
    
        
    
        
        
        
        
        