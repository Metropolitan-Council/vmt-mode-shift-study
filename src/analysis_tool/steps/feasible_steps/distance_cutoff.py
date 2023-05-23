import pandas as pd
import matplotlib.pyplot as plt

from steps.parent_classes import ContinuousStep
from steps.mode_enum import Mode
from steps.figure_lib import *

import inspect

class WalkDistanceStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "feasible_walking_dist", Mode.WALK, cutoff, "walk_distance_miles")
        self.df.loc[:, "walk_distance_miles"] = self.df["walk_distance_meters"] * 0.000621371
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in [self.mode, Mode.CAR]], percentile=self.cutoff)
    
    def get_summary_figure(self):
        fig, ax = plot_mode_density(self.df, [(self.mode, self.column_name), (Mode.CAR, self.column_name)], percentile=self.cutoff) 
        ax.set_xlim(left=0, right=10)
        plt.title("Rerouted walk distance distributions for canonical walk and car trips")
        return fig, ax
    
    def apply_step(self) -> None:
        super().apply_step(self.df[self.column_name] > self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("Walk trips are generally short.  Here we consider the trip length distribution of walking trips, and set a maximum allowable distance to be considered feasible to walk. The parameter for this can be seen near the beginning of the document, but the default is the 95th percentile of the distances of the observed walking trips.")
        
        # summary figure
        res.append("""In this figure, the distributions for walking distances from the rerouting analysis for observed walk trips can be seen, alongside the distributions for calculated re-routing walking distances for observed car trips. It is readily seen that the car trip walking distances are far more right-skewed than the walking trip walking distances, which is to be expected, as car trips are more likely to be used for long distance trips. 

        Of note are the two lines present in the graph, which represent the percentiles of the data specified as a parameter. In particular, any part of the orange distribution to the left of the blue line is within the threshold for feasibility (for the given percentile cutoff) and thus constitutes a feasible mode shift.""")
        
        # summary statistics
        res.append("Here, the summary statistics for walk trip walk distances and car trip car distances can be seen. This largely reflects the distribution seen above, although the percentile given as a parameter is quantified here.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
        
    
class BikeDistanceStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "feasible_biking_dist", Mode.BIKE, cutoff, "bike_distance_miles")
        self.df.loc[:, "bike_distance_miles"] = self.df["bike_distance_meters"] * 0.000621371
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in [self.mode, Mode.CAR]], percentile=self.cutoff)
    
    def get_summary_figure(self):
        fig, ax = plot_mode_density(self.df, [(self.mode, self.column_name), (Mode.CAR, self.column_name)], percentile=self.cutoff) 
        ax.set_xlim(left=0, right=25)
        plt.title("Rerouted bike distance distributions for canonical bike and car trips")
        return fig, ax
    
    def apply_step(self) -> None:
        super().apply_step(self.df[self.column_name] > self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("Bike trips are generally on the shorter side.  Here we consider the trip length distribution of walking trips, and set a maximum allowable distance to be considered feasible to walk (as before, this can be specified in the parameter section). By default, the maximum allowable distance is the 95th percentile of distances of the observed biking trips. ")
        
        # summary figure
        res.append("""In this figure, we can see a comparison between the distributions of biking distance for observed biking trips versus biking distance if observed car trips were to shift to biking. The car distance distribution is more right-skewed, which is reasonable as cars generally go longer distances. The line here represents the specified percentile of each distribution, and all trips of the orange distribution to the left of the blue line can feasibly switch to biking, as their biking distance is reasonable compared to observed biking distances.""")
        
        # summary statistics
        res.append("Below, we can see summary statistics for biking/car biking distance. This largely reflects what was seen in the above figure, but with more quantifiable values.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res