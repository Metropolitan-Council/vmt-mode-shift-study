import pandas as pd
import matplotlib.pyplot as plt

from steps.parent_classes import ContinuousStep
from steps.mode_enum import Mode
from steps.figure_lib import *

class BikeSnowDepthStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "feasible_snow_depth", Mode.BIKE, cutoff)
        
        self.column_name = "snow_depth"
        self.categories = [[x, self.column_name] for x in [self.mode, Mode.CAR]]
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=self.categories, percentile=self.cutoff)
    
    def get_summary_figure(self):
        fig, ax = plot_mode_density(self.df, [(self.mode, self.column_name), (Mode.CAR, self.column_name)], percentile=self.cutoff) 
        ax.set_xlim(left=0, right=10)
        plt.title("Snow depth during travel day for canonical bike and car trips")
        return fig, ax
    
    def apply_step(self):
        super().apply_step(self.df[self.column_name] > self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
    
    
class BikeHighLTSDistStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        pass