import pandas as pd
import matplotlib.pyplot as plt

from steps.parent_classes import ContinuousStep, CategoricalStep
from steps.figure_lib import *
from steps.enums import *

import inspect

class TransitTransferCountStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.01):
        super().__init__(df, "likely_transit_transfer_number", Mode.TRANSIT, cutoff, "transit_num_transfers", OverallStep.PROBABLE)
    
    def get_summary_statistics(self):
        return show_summaries(self.df, [[x, self.column_name] for x in [self.mode, Mode.CAR]], self.get_cutoff_pct())
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.column_name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.column_name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Re-routed transfer counts for canonical transit trips")
        ax[1].set_title("Re-routed transfer counts for canonical car trips")
        
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
        res.append("""Transfers are a very costly and inconvenient part of going on transit, which makes it a good indicator for whether a trip can more likely switch to transit. Here, we only consider transit trips that require 0 transfers more likely.""")
        
        # summary figure
        res.append("""Observe that the number of transfers for observed transit trips are more left-skewed than those for observed car trips, showing that transfer number is indeed an important indicator for trip likelihood (this could be a reflection of rerouting restrictions, though).""")
        
        # summary statistics
        res.append("The summary statistics for the figure above is shown below.")
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res