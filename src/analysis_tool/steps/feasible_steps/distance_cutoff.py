import pandas as pd
import sys

sys.path.append("..")

from parent_classes import ContinuousStep
from figure_lib import *
from misc import *

class WalkDistanceStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "feasible_walking_dist", "walk", cutoff)
        self.categories = [[x, "walk_distance_miles"] for x in ["Walk", "Car"]]
        
        self.prev = df["feasible_walk_shift"].copy()
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=self.categories, percentile=self.cutoff)
    
    def get_summary_figure(self):
        fig, ax = plot_mode_density(self.df, [('Walk','walk_distance_miles'), ('Car','walk_distance_miles')], percentile=self.cutoff) 
        ax.set_xlim(left=0, right=10)
        plt.title("Observed versus rerouted distance distributions for canonical walk trips")
        return fig, ax
    
    def apply_step(self):
        super().apply_step(self.df["walk_distance_miles"] > self.df[self.df["mode"] == "Walk"]["walk_distance_miles"].quantile(self.cutoff), self.prev)
        
    def get_statistics(self):
        return super().get_statistics("walk", self.prev)
    
    def get_map(self):
        return super().get_map()
        