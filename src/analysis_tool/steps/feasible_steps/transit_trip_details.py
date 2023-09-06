import pandas as pd
import matplotlib.pyplot as plt

from steps.parent_classes import ContinuousStep, CategoricalStep
from steps.figure_lib import *
from steps.enums import *

import inspect

class TransitAccessDistanceStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "feasible_transit_access_distance", Mode.TRANSIT, cutoff, "transit_access_length_miles", Phase.FEASIBLE, "miles")
        
        self.df.loc[:, "transit_access_length_miles"] = df["transit_access_length"] * 0.000621371
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in [self.mode, Mode.CAR]], percentile=self.get_cutoff_pct())
    
    def get_summary_figure(self):
        fig = plot_density_plotly(self.df, self.mode, self.column_name, self.get_cutoff_pct())
        fig.update_layout(
            title=dict(
                text="Rerouted transit access distance for observed transit and car trips",
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
                text="Access Distance (miles)",
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
    
    def __repr__(self):
        return super().__repr__() + ". NOTE: With the current rerouting methodology, this step is superseded by assumptions made during rerouting."
    
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""Transit trips are a bit more complicated, because they come in several legs.  For example: 

        Leg 1: Walk to Bus Stop
        Leg 2: Ride Bus to Another Stop
        Leg 3: Walk to Destination
                   
        Here we consider the maximum walking distance to or from a bus stop.  Here we can treat each walking leg on a transit trip as a separate observation.

        It should be noted that currently, the transit re-routing already restricts the possibilty of switching to a transit trip, as it only returns a trip if the re-routing conditions are satisifed. This means this condition is already implicitly enforced in the re-routing analysis.""")
        
        # summary figure
        res.append("""Below is a comparison between the distributions of the distance to a transit stop for observed transit versus that for observed car trips (re-routing data was used for both distributions to allow for a fairer comparison). It can be seen that generally, observed transit trips tend to have lower distances to transit stops, which makes sense as observed transit trips likely find transit attractive in some way, and this is one way it could be attractive to them.

        The lines indicate the specified percentile of each of the distributions, and all of the orange distribution to the left of the blue line represent car trips that can feasibly switch to transit, when considering the access distance indicator. At the default 95th percentile, it can be seen that all these trips can feasibly shift, as this represents re-routing distances, which already account for this factor when re-routing was then. """)
        
        # summary statistics
        res.append("Here, the summary statistics for observed transit vs observed car trip distance to a transit stop can be seen, with the former drawing on the estimated TBI data and the latter drawing on the re-routing analysis. The specified percentile of the left column, drawing to some degree on the canoncial TBI data, can be used to determine the feasibility cutoff, which, at the default 95th percentile, is about 1.42. ")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
    
class TransitTransferCountStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "feasible_transit_transfer_number", Mode.TRANSIT, cutoff, "transit_num_transfers", Phase.FEASIBLE, "transfers")
    
    def get_summary_statistics(self):
        return show_summaries(self.df, [[x, self.column_name] for x in [self.mode, Mode.CAR]], self.get_cutoff_pct())
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.column_name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.column_name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Re-routed transfer counts for observed transit trips")
        ax[1].set_title("Re-routed transfer counts for observed car trips")
        
        return fig, ax
    
    def apply_step(self):
        if self.cutoff_mode == CutoffMode.PCT:
            super().apply_step(self.df[self.column_name] > self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
        elif self.cutoff_mode == CutoffMode.RAW:
            super().apply_step(self.df[self.column_name] > self.cutoff)
        else:
            raise RuntimeError("Something went wrong with the cutoff mode enum")
        
    def __repr__(self):
        return super().__repr__() + ". NOTE: With the current rerouting methodology, this step is superseded by assumptions made during rerouting."
    
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""Transfers from one transit medium to another is generally a deterrent and inconvenience to passengers riding transit. Here, we consider the maximum number of transit transfers that would still be feasible for an individual that would potentially be switching to a transit mode from another. By default, this cutoff is the 95th percentile of the observed transit trips, and this would be 3 transfers. 

        This indicator suffers from the same issues as the access distance indicator does, as it is already accounted for in the re-routing analysis for transit.""")
        
        # summary figure
        res.append("""Below, the distribution of the number of transfers for observed transit trips can be seen on the left and the distribution of the number of transfers for observed car trips can be seen on the right (using the re-routing data). Both of these distributions draw on the re-routing analysis to allow for a fairer comparison. It can overall be seen that car trips, if switched to transit, tend to have more transfers. """)
        
        # summary statistics
        res.append("Below, the summary statistics for transfers for observed transit and observed car trips can be seen, with the former drawing on the TBI data and the latter drawing on the re-routing analysis. The specified percentile in the transit transfers column can be used as the feasibility cutoff. ")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
class TransitReroutedStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame, column="transit_duration", scenario=False):
        super().__init__(df, "feasible_transit_route_found", Mode.TRANSIT, Phase.FEASIBLE)
        
        # make the name distinct if we are at a scenario
        if scenario:
            self.name = self.name + "_scenario_" + column
        
        self.df.loc[:, self.name] = ~self.df[column].isna()
        
    def get_summary_statistics(self):
        return show_value_counts(self.df, [[x, self.name] for x in [self.mode, Mode.CAR]])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Whether a trip had a valid rerouted\ntrip for observed transit trips")
        ax[1].set_title("Whether a trip had a valid rerouted\ntrip for observed car trips")
        
        return fig, ax
    
    def apply_step(self):
        super().apply_step(~self.df[self.name])
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""This indicator, which reflects whether the re-rerouting analysis returned a valid transit trip for a given trip, supersedes the previous two sections, covering both access distance/transfer count. Thus, by applying this indicator, we effectively apply the previous two simultaneously, restricting the percentage of car trips that can feasibly shift to transit substantially.""")
        
        # summary figure
        res.append("""Placeholder""")
        
        # summary statistics
        res.append("Placeholder")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res