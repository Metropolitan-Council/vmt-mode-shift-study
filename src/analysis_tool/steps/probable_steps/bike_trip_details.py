import pandas as pd
import matplotlib.pyplot as plt

from steps.parent_classes import ContinuousStep
from steps.enums import Mode, CutoffMode
from steps.figure_lib import *

import inspect
    
class BikeHighLTSDistStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.01):
        super().__init__(df, "probable_bike_high_lts_dist", Mode.BIKE, cutoff, "high_lts_dist")
        
        df.loc[:, "high_lts_dist"] = df["bike_distance_meters_3"] + df["bike_distance_meters_4"]
        df.loc[:, "high_lts_biking_pct"] = df["high_lts_dist"] / df["bike_distance_meters"]
        
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in [self.mode, Mode.CAR]], percentile=self.get_cutoff_pct())
    
    def get_summary_figure(self):
        fig, ax = plot_mode_density(self.df, [(self.mode, self.column_name), (Mode.CAR, self.column_name)], percentile=self.get_cutoff_pct()) 
        ax.set_xlim(left=0, right=1)
        plt.title(r"High LTS (3/4) distance for canonical bike and car trips")
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
        res.append("""In the feasibility analysis, we had a similar constraint on the % of LTS (level of traffic stress), but now, we impose a stricter restriction on high stress distance.""")
        
        # summary figure
        res.append("""The comparison of the distribution between bike/car lts distance can be seen below. This reflects what was seen in the feasibilty analysis, with bike trips tending to have lower absolute lts distances.""")
        
        # summary statistics
        res.append("The summary statistics can be found below.")
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res