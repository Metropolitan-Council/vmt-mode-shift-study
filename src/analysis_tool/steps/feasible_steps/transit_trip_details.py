import pandas as pd
import matplotlib.pyplot as plt

from steps.parent_classes import ContinuousStep, CategoricalStep, Mode
from steps.figure_lib import *

class TransitAccessDistanceStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "feasible_transit_access_distance", Mode.TRANSIT, cutoff)
        
        self.df.loc[:, "transit_access_length_miles"] = df["transit_access_length"] / 1609.34
        self.column_name = "transit_access_length_miles"
        self.categories = [[x, self.column_name] for x in [self.mode, Mode.CAR]]
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=self.categories, percentile=self.cutoff)
    
    def get_summary_figure(self):
        fig, ax = plot_mode_density(self.df, [(self.mode, self.column_name), (Mode.CAR, self.column_name)], percentile=self.cutoff) 
        ax.set_xlim(left=0, right=10)
        plt.title("Rerouted transit access distance for canonical transit and car trips")
        return fig, ax
    
    def apply_step(self):
        super().apply_step(self.df[self.column_name] > self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
    
    def __repr__(self):
        return super().__repr__() + ". NOTE: With the current rerouting methodology, this step is superseded by assumptions made during rerouting."
    
    
class TransitTransferCountStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "feasible_transit_transfer_number", Mode.TRANSIT, cutoff)
        
        self.column_name = "transit_num_transfers"
        self.categories = [[x, self.column_name] for x in [self.mode, Mode.CAR]]
    
    def get_summary_statistics(self):
        return show_summaries(self.df, self.categories, self.cutoff)
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.column_name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.column_name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Re-routed transfer counts for canonical transit trips")
        ax[1].set_title("Re-routed transfer counts for canonical car trips")
        
        return fig, ax
    
    def apply_step(self):
        super().apply_step(self.df[self.column_name] > self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
        
    def __repr__(self):
        return super().__repr__() + ". NOTE: With the current rerouting methodology, this step is superseded by assumptions made during rerouting."
    
class TransitReroutedStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df, "feasible_transit_route_found", Mode.TRANSIT)
        
        self.df.loc[:, "valid_transit_route"] = ~self.df["transit_trip_id"].isna()
        self.column_name = "valid_transit_route"
        self.categories = [[x, self.column_name] for x in [self.mode, Mode.CAR]]
        
    def get_summary_statistics(self):
        return self.df[self.column_name].value_counts()
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.column_name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.column_name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Whether a trip had a valid rerouted trip for canonical transit trips")
        ax[1].set_title("Whether a trip had a valid rerouted trip for canonical car trips")
        
        return fig, ax
    
    def apply_step(self):
        super().apply_step(~self.df[self.column_name])