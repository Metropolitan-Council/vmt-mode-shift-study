import pandas as pd
import matplotlib.pyplot as plt

from steps.parent_classes import ContinuousStep
from steps.figure_lib import *

class WalkDistanceStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "feasible_walking_dist", "walk", cutoff)
        self.categories = [[x, "walk_distance_miles"] for x in ["Walk", "Car"]]
        
        self.prev = pd.to_numeric(df["feasible_walk_shift"].copy())
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=self.categories, percentile=self.cutoff)
    
    def get_summary_figure(self):
        fig, ax = plot_mode_density(self.df, [('Walk','walk_distance_miles'), ('Car','walk_distance_miles')], percentile=self.cutoff) 
        ax.set_xlim(left=0, right=10)
        plt.title("Rerouted walk distance distributions for canonical walk and car trips")
        return fig, ax
    
    def apply_step(self):
        print(self.df["walk_distance_miles"] > self.df[self.df["mode"] == "Walk"]["walk_distance_miles"].quantile(self.cutoff))
        super().apply_step(self.df["walk_distance_miles"] > self.df[self.df["mode"] == "Walk"]["walk_distance_miles"].quantile(self.cutoff), self.prev)
        
    def get_step_statistics(self):
        return super().get_statistics(self.prev)
    
    def get_map(self):
        return super().get_map()
    
class BikeDistanceStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "feasible_biking_dist", "bike", cutoff)
        self.categories = [[x, "bike_weight"] for x in ["Bike/Scooter", "Car"]]
        
        self.prev = df["feasible_bike_shift"].copy()
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=self.categories, percentile=self.cutoff)
    
    def get_summary_figure(self):
        fig, ax = plot_mode_density(self.df, [('Bike/Scooter','bike_weight'), ('Car','bike_weight')], percentile=self.cutoff) 
        ax.set_xlim(left=0, right=10)
        plt.title("Rerouted bike distance distributions for canonical bike and car trips")
        return fig, ax
    
    def apply_step(self):
        super().apply_step(self.df["bike_weight"] > self.df[self.df["mode"] == "Bike/Scooter"]["bike_weight"].quantile(self.cutoff), self.prev)
        
    def get_step_statistics(self):
        return super().get_statistics(self.prev)
    
    def get_map(self):
        return super().get_map()
        