from typing import List
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px

from steps.parent_classes import ContinuousStep
from steps.enums import *
from steps.figure_lib import *

import inspect

class WalkDistanceStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95, column="walk_distance_rerouted", scenario=False):
        super().__init__(df, "feasible_walking_dist", Mode.WALK, cutoff, column, Phase.FEASIBLE, "miles")
        
        # make the name distinct if we are at a scenario
        if scenario:
            self.name = self.name + "_scenario_" + column
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in [self.mode, Mode.CAR]], percentile=self.get_cutoff_pct(), column_names=["Walk distance in miles if walking chosen (observed walk trips)", "Walk distance in miles if walking chosen (observed car trips)"])
    
    def get_summary_figure(self):
        fig = plot_density_plotly(self.df, self.mode, self.column_name, self.get_cutoff_pct())
        fig.update_layout(
            title=dict(
                text="Rerouted walk distance distributions<br>for observed walk and car trips",
                font=dict(size=18),
                x=0.5,
                y=0.9,
                xanchor='center',
            ),
            xaxis_title=dict(
                text="Walk Distance (miles)",
                font=dict(size=16)
            ),
            yaxis_title=dict(
                text="Probability Density",
                font=dict(size=16)
            ),
            legend=dict(
                title="Legend",
                font=dict(size=16)
            )
        )
        return fig
    
    def apply_step(self) -> None:
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
        res.append("Walk trips are generally short.  Here we consider the trip length distribution of walking trips, and set a maximum allowable distance to be considered feasible to walk. The parameter for this can be seen near the beginning of the document, but the default is the 95th percentile of the distances of the observed walking trips.")
        
        # summary figure
        res.append("""In this figure, the distributions for walking distances from the rerouting analysis for observed walk trips can be seen, alongside the distributions for calculated re-routing walking distances for observed car trips. It is readily seen that the car trip walking distances are far more right-skewed than the walking trip walking distances, which is to be expected, as car trips are more likely to be used for long distance trips. 

        Of note are the two lines present in the graph, which represent the percentiles of the data specified as a parameter. In particular, any part of the orange distribution to the left of the blue line is within the threshold for feasibility (for the given percentile cutoff) and thus constitutes a feasible mode shift.""")
        
        # summary statistics
        res.append("Here, the summary statistics for trip walk distances when segmented by observed TBI mode (e.g., if an actual car trip shifted to walk, what would be the walk distance of the resultant trip) can be seen. This largely reflects the distribution seen above, although the percentile given as a parameter is quantified here.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
    @staticmethod
    def get_default_cols():
        return ["walk_distance_rerouted"]
        
    
class BikeDistanceStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95, column="bike_distance_rerouted", scenario=False):
        super().__init__(df, "feasible_biking_dist", Mode.BIKE, cutoff, column, Phase.FEASIBLE, "miles")
            
        # make the name distinct if we are at a scenario
        if scenario:
            self.name = self.name + "_scenario_" + column
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in [self.mode, Mode.CAR]], percentile=self.get_cutoff_pct(), column_names=["Bike distance in miles if biking chosen (observed bike trips)", "Bike distance in miles if biking chosen (observed car trips)"])
    
    def get_summary_figure(self):
        fig = plot_density_plotly(self.df, self.mode, self.column_name, self.get_cutoff_pct())
        fig.update_layout(
            title=dict(
                text="Rerouted bike distance distributions<br>for observed bike and car trips",
                font=dict(size=18),
                x=0.5,
                y=0.9,
                xanchor='center',
            ),
            xaxis_title=dict(
                text="Bike Distance (miles)",
                font=dict(size=16)
            ),
            yaxis_title=dict(
                text="Probability Density",
                font=dict(size=16)
            ),
            legend=dict(
                title="Legend",
                font=dict(size=16)
            )
        )
        return fig
    
    def apply_step(self) -> None:
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
        res.append("Bike trips are generally on the shorter side.  Here we consider the trip length distribution of biking trips, and set a maximum allowable distance to be considered feasible to bike (as before, this can be specified in the parameter section). By default, the maximum allowable distance is the 95th percentile of distances of the observed biking trips. ")
        
        # summary figure
        res.append("""In this figure, we can see a comparison between the distributions of biking distance for observed biking trips versus biking distance if observed car trips were to shift to biking. The car distance distribution is more right-skewed, which is reasonable as cars generally go longer distances. The line here represents the specified percentile of each distribution, and all trips of the orange distribution to the left of the blue line can feasibly switch to biking, as their biking distance is reasonable compared to observed biking distances.""")
        
        # summary statistics
        res.append("Here, the summary statistics for trip bike distances when segmented by observed TBI mode (e.g., if an actual car trip shifted to bike, what would be the bike distance of the resultant trip) can be seen. This largely reflects the distribution seen above, although the percentile given as a parameter is quantified here.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
    @staticmethod
    def get_default_cols() -> List[str]:
        return ["bike_distance_rerouted"]