import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

from steps.parent_classes import ContinuousStep
from steps.enums import *
from steps.figure_lib import *

import inspect

class WalkDurationDifferenceStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "likely_walking_car_duration_difference", Mode.WALK, cutoff, "car_minus_walk_minutes", Phase.PROBABLE)
        self.df.loc[:, "car_minus_walk_minutes"] = df["car_duration_seconds_adj"] / 60 - df["walk_duration_seconds"] / 60
        self.cutoff = stats.percentileofscore(self.df[self.df["mode"] == self.mode]["car_minus_walk_minutes"], -15) / 100
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in [self.mode, Mode.CAR]], percentile=self.get_cutoff_pct())
    
    def get_summary_figure(self):
        fig = plot_density_plotly(self.df, self.mode, self.column_name, self.get_cutoff_pct())
        fig.update_layout(
            title={
                'text': r"Difference between car and walk rerouted durations",
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            xaxis_title="Probability Density",
            yaxis_title="Duration Difference (minutes)",
            legend_title="Legend"
        )
        return fig
    
    def apply_step(self) -> None:
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
        res.append("Even if switching from a car mode to a non-car mode is considered feasible in terms of the factors discussed previously, a person may not be likely to choose to do so if the time difference is too great.")
        
        # summary figure
        res.append("""Below, a distribution of the difference between rerouted car trip and walk trip durations are shown for both observed car and walk trips.

        The specified percentile is also shown with vertical lines. The percentiles are flipped here as the left represents more un-ideal conditions, which makes the consideration of these flipped percentiles more meaningful in gauging trip shift likelihood.""")
                
        # summary statistics
        res.append("Below we can see the summary statistics for the above distribution. Nothing is too shocking, with the statistics reflecting what was seen with the graph.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res

class BikeDurationDifferenceStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "likely_biking_car_duration_difference", Mode.BIKE, cutoff, "car_minus_bike_minutes", Phase.PROBABLE)
        self.df.loc[:, "car_minus_bike_minutes"] = df["car_duration_seconds_adj"] / 60 - df["bike_duration_seconds_adj"] / 60
        self.cutoff = stats.percentileofscore(self.df[self.df["mode"] == self.mode]["car_minus_bike_minutes"], -15) / 100
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in [self.mode, Mode.CAR]], percentile=self.get_cutoff_pct())
    
    def get_summary_figure(self):
        fig = plot_density_plotly(self.df, self.mode, self.column_name, self.get_cutoff_pct())
        fig.update_layout(
            title={
                'text': r"Difference between car and bike rerouted durations",
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            xaxis_title="Probability Density",
            yaxis_title="Duration Difference (minutes)",
            legend_title="Legend"
        )
        return fig
    
    def apply_step(self) -> None:
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
        res.append("Even if switching from a car mode to a non-car mode is considered feasible in terms of the factors discussed previously, a person may not be likely to choose to do so if the time difference is too great.")
        
        # summary figure
        res.append("""Below, a distribution of the difference between rerouted car trip and bike trip durations are shown for both observed car and bike trips.

        The specified percentile is also shown with vertical lines. The percentiles are flipped here as the left represents more un-ideal conditions, which makes the consideration of these flipped percentiles more meaningful in gauging trip shift likelihood.""")
                
        # summary statistics
        res.append("Below we can see the summary statistics for the above distribution. Nothing is too shocking, with the statistics reflecting what was seen with the graph.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
    
class TransitDurationDifferenceStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "likely_transit_car_duration_difference", Mode.TRANSIT, cutoff, "car_minus_transit_minutes", Phase.PROBABLE)
        self.df.loc[:, "car_minus_transit_minutes"] = df["car_duration_seconds_adj"] / 60 - df["transit_duration"]

        self.cutoff = stats.percentileofscore(self.df[(self.df["mode"] == self.mode) & ~self.df["car_minus_transit_minutes"].isna()]["car_minus_transit_minutes"], -15) / 100
    
    def get_summary_statistics(self):
        return show_summaries(self.df[~self.df["transit_duration"].isna()], modes=[[x, self.column_name] for x in [self.mode, Mode.CAR]], percentile=self.get_cutoff_pct())
    
    def get_summary_figure(self):
        fig = plot_density_plotly(self.df[~self.df["transit-duration"].isna()], self.mode, self.column_name, self.get_cutoff_pct())
        fig.update_layout(
            title={
                'text': r"Difference between car and transit rerouted durations",
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            xaxis_title="Probability Density",
            yaxis_title="Duration Difference (minutes)",
            legend_title="Legend"
        )
        return fig
    
    def apply_step(self) -> None:
        if self.cutoff_mode == CutoffMode.PCT:
            super().apply_step(self.df[self.column_name] < self.df[(self.df["mode"] == self.mode) & ~self.df["car_minus_transit_minutes"].isna()][self.column_name].quantile(self.cutoff))
        elif self.cutoff_mode == CutoffMode.RAW:
            super().apply_step(self.df[self.column_name] < self.cutoff)
        else:
            raise RuntimeError("Something went wrong with the cutoff mode enum")
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("Even if switching from a car mode to a non-car mode is considered feasible in terms of the factors discussed previously, a person may not be likely to choose to do so if the time difference is too great.")
        
        # summary figure
        res.append("""Below, a comparison of the distributions for observed transit trip car minus tranist duration and observed car trip car minus transit duration (rerouting as needed) can be seen.

        Interestingly, here we observe a deviation from the graphs in the previous section, with observed transit trips having higher duration differences than their corresponding cars. As such, with a duration difference restriction, a good amount of car trips are still more likely shift to transit.

        There also appear to be more car trips that could actually be faster when taken on transit here. This could be due to the more stringent restrictions placed upon transit trips in the feasibility analysis section.""")
                
        # summary statistics
        res.append("The summary statistics for this graph can be found below.")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res