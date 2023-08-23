import pandas as pd
import matplotlib.pyplot as plt

from steps.parent_classes import ContinuousStep
from steps.enums import *
from steps.figure_lib import *

import inspect

class WalkPrecipitationStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0):
        super().__init__(df, "likely_walk_precipitation", Mode.WALK, cutoff, "precipitation", Phase.PROBABLE)
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in Mode.get_all()], percentile=self.get_cutoff_pct(), column_names=["Precipitation in 1/10 mm on travel day if walking chosen (observed walk trips)", "Precipitation in 1/10 mm on travel day if walking chosen (observed car trips)"])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(figsize=(12, 6))
        #plot_mode_density(self.df, [(x, "snow_depth") for x in [Mode.BIKE, Mode.CAR, Mode.TRANSIT, Mode.WALK]], percentile=self.get_cutoff_pct()) 
        sns.boxplot(data=self.df, x=self.column_name, y="mode", ax=ax)
        plt.title("Precipitation during travel day for all modes")
        return fig, ax
    
    def apply_step(self):
        if self.cutoff_mode == CutoffMode.PCT:
            super().apply_step(self.df[self.column_name] > self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
        elif self.cutoff_mode == CutoffMode.RAW:
            super().apply_step(self.df[self.column_name] > self.cutoff)
        else:
            raise RuntimeError("Something went wrong with the cutoff mode enum")
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""Weather plays an important consideration when determining whether a car trip is more likely to switch to an alternative mode, as cars offer a higher baseline for weather tolerance than these alternative modes. This is especially pronounced for biking and walking, which offer no protection to the elements, as seen in the feasibility section with the biking in snow indicator.""")
        
        # summary figure
        res.append("""A comparison of the distribution of precipitation amounts segmented by mode show the importance of precipitation--for bike/scooter and particularly walking, the 95th percentile of precipitation on trips is significantly lower than that for car and transit trips. The walk percentile is not seen at the 95th because it overlaps directly with bike/scooter.""")
        
        # summary statistics
        res.append("Summary statistics for these distributions are found below.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
class BikePrecipitationStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0):
        super().__init__(df, "likely_bike_precipitation", Mode.BIKE, cutoff, "precipitation", Phase.PROBABLE)
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in Mode.get_all()], percentile=self.get_cutoff_pct(), column_names=["Precipitation in 1/10 mm on travel day if biking chosen (observed bike trips)", "Precipitation in 1/10 mm on travel day if biking chosen (observed car trips)"])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(figsize=(12, 6))
        #plot_mode_density(self.df, [(x, "snow_depth") for x in [Mode.BIKE, Mode.CAR, Mode.TRANSIT, Mode.WALK]], percentile=self.get_cutoff_pct()) 
        sns.boxplot(data=self.df, x=self.column_name, y="mode", ax=ax)
        plt.title("Precipitation during travel day for all modes")
        return fig, ax
    
    def apply_step(self):
        if self.cutoff_mode == CutoffMode.PCT:
            super().apply_step(self.df[self.column_name] > self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
        elif self.cutoff_mode == CutoffMode.RAW:
            super().apply_step(self.df[self.column_name] > self.cutoff)
        else:
            raise RuntimeError("Something went wrong with the cutoff mode enum")
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""Weather plays an important consideration when determining whether a car trip is more likely to switch to an alternative mode, as cars offer a higher baseline for weather tolerance than these alternative modes. This is especially pronounced for biking and walking, which offer no protection to the elements, as seen in the feasibility section with the biking in snow indicator.""")
        
        # summary figure
        res.append("""A comparison of the distribution of precipitation amounts segmented by mode show the importance of precipitation--for bike/scooter and particularly walking, the 95th percentile of precipitation on trips is significantly lower than that for car and transit trips. The walk percentile is not seen at the 95th because it overlaps directly with bike/scooter.""")
        
        # summary statistics
        res.append("Summary statistics for these distributions are found below.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
class WalkTemperatureStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0):
        super().__init__(df, "likely_walk_temperature", Mode.WALK, cutoff, "temperature", Phase.PROBABLE)
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in Mode.get_all()], percentile=self.get_cutoff_pct(), column_names=["Temperature in 1/10 C on travel day if walking chosen (observed walk trips)", "Temperature in 1/10 C on travel day if walking chosen (observed car trips)"])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(figsize=(12, 6))
        #plot_mode_density(self.df, [(x, "snow_depth") for x in [Mode.BIKE, Mode.CAR, Mode.TRANSIT, Mode.WALK]], percentile=self.get_cutoff_pct()) 
        sns.boxplot(data=self.df, x=self.column_name, y="mode", ax=ax)
        plt.title("Average temperature during travel day for all modes")
        return fig, ax
    
    def apply_step(self):
        if self.cutoff_mode == CutoffMode.PCT:
            super().apply_step(self.df[self.column_name] < self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
        elif self.cutoff_mode == CutoffMode.RAW:
            super().apply_step(self.df[self.column_name] < self.cutoff)
        else:
            raise RuntimeError("Something went wrong with the cutoff mode enum")
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""A tangential topic to rainfall in the topic of likely walk/bike shifts is temperature. As with rainfall, the modes of walking/biking are far more susceptible to temperature than car/transit trips are, making it another consideration for whether a trip shift is more likely to switch.
                   
        NOTE: the cutoff direction is flipped here; the cutoff is the lower bound for the temperature""")
        
        # summary figure
        res.append("""A distribution of average temperatures over the day a linked trip occurred on segmented by mode can be seen below. As with duration difference, we flip the percentile for a more meaningful analysis. Also observe that biking/walking trips tend to occur in higher temperatures than transit/car, reflecting the reasoning discussed earlier.""")
        
        # summary statistics
        res.append("The summary statistics for this distribution can be found below.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
class BikeTemperatureStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0):
        super().__init__(df, "likely_bike_temperature", Mode.BIKE, cutoff, "temperature", Phase.PROBABLE)
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in Mode.get_all()], percentile=self.get_cutoff_pct(), column_names=["Temperature in 1/10 C on travel day if biking chosen (observed bike trips)", "Temperature in 1/10 C on travel day if biking chosen (observed car trips)"])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(figsize=(12, 6))
        #plot_mode_density(self.df, [(x, "snow_depth") for x in [Mode.BIKE, Mode.CAR, Mode.TRANSIT, Mode.WALK]], percentile=self.get_cutoff_pct()) 
        sns.boxplot(data=self.df, x=self.column_name, y="mode", ax=ax)
        plt.title("Average temperature during travel day for all modes")
        return fig, ax
    
    def apply_step(self):
        if self.cutoff_mode == CutoffMode.PCT:
            super().apply_step(self.df[self.column_name] < self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
        elif self.cutoff_mode == CutoffMode.RAW:
            super().apply_step(self.df[self.column_name] < self.cutoff)
        else:
            raise RuntimeError("Something went wrong with the cutoff mode enum")
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""A tangential topic to rainfall in the topic of likely walk/bike shifts is temperature. As with rainfall, the modes of walking/biking are far more susceptible to temperature than car/transit trips are, making it another consideration for whether a trip shift is more likely to switch.
                   
        NOTE: the cutoff direction is flipped here; the cutoff is the lower bound for the temperature""")
        
        # summary figure
        res.append("""A distribution of average temperatures over the day a linked trip occurred on segmented by mode can be seen below. As with duration difference, we flip the percentile for a more meaningful analysis. Also observe that biking/walking trips tend to occur in higher temperatures than transit/car, reflecting the reasoning discussed earlier.""")
        
        # summary statistics
        res.append("The summary statistics for this distribution can be found below.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res