import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Dict

from steps.parent_classes import ContinuousStep
from steps.enums import *
from steps.figure_lib import *

import inspect
    
class BikeHighLTSDistStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, inputs: Dict[str, str], cutoff: float=0.01):
        super().__init__(df, "probable_bike_high_lts_dist", inputs, Mode.BIKE, cutoff, "high_lts_dist", Phase.PROBABLE, "meters")
        
        # df.loc[:, "high_lts_dist"] = df["bike_distance_lts_3_rerouted"] + df["bike_distance_lts_4_rerouted"]
        # df.loc[:, "high_lts_biking_pct"] = df["high_lts_dist"] / df["bike_distance_rerouted"]
        
    @staticmethod
    def get_mode() -> Mode:
        return Mode.BIKE
        
    @staticmethod
    def process_inputs(inputs: Dict[str, pd.Series]) -> pd.Series:
        return inputs["lts3_distance"] + inputs["lts4_distance"]
        
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in [self.mode, Mode.CAR]], percentile=self.get_cutoff_pct(), column_names=["High LTS distance proportion if biking chosen (observed car trips)", "High LTS distance proportion if biking chosen (observed bike trips)"])
    
    def get_summary_figure(self):
        fig = plot_density_plotly(self.df, self.mode, self.column_name, self.get_cutoff_pct())
        fig.update_layout(
            title=dict(
                text=r"High LTS (3/4) distance for observed bike and car trips",
                font=dict(size=18),
                x=0.5,
                y=0.9,
                xanchor='center',
            ),
            xaxis_title=dict(
                text="Probability Density",
                font=dict(size=16)
            ),
            yaxis_title=dict(
                text="High LTS Distance (meters)",
                font=dict(size=16)
            ),
            legend=dict(
                title="Legend",
                font=dict(size=16)
            )
        )
        return fig
    
    def apply_step(self):
        if self.cutoff_mode == CutoffMode.PCT:
            super().apply_step(self.df[self.column_name] > self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
        elif self.cutoff_mode == CutoffMode.RAW:
            super().apply_step(self.df[self.column_name] > self.cutoff)
        else:
            raise RuntimeError("Something went wrong with the cutoff mode enum")
        
    def get_text(self) -> List[str]:
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