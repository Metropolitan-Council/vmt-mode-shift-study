import pandas as pd
import matplotlib.pyplot as plt

from steps.parent_classes import CategoricalStep
from steps.enums import Mode, CutoffMode
from steps.figure_lib import *

import inspect

import sys
sys.path.append("...")
from settings import handler

class WalkPurposeStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df, "likely_walk_purpose", Mode.WALK)
        
        df["purpose_cleaned"] = df["d_purpose_category"]
        df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["School", "School-related"]), "School", df["purpose_cleaned"])
        df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Work", "Work-related"]), "Work", df["purpose_cleaned"])
        df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Errand/Other", "Errand"]), "Errand", df["purpose_cleaned"])
        df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Shop", "Shopping"]), "Shop", df["purpose_cleaned"])
        df["purpose_cleaned"] = np.where(df["purpose_cleaned"].isin(["Missing: Non-response", "Missing: Skip logic", "Not imputable"]), "Missing", df["purpose_cleaned"])
        
        self.df.loc[:, self.name] = ~self.df["purpose_cleaned"].isin(handler["unlikely_purposes"])
        
    def get_summary_statistics(self):
        return show_value_counts(self.df[self.df["purpose_cleaned"] != "Missing"], [[x, self.name] for x in [self.mode, Mode.CAR]])
    
    def get_summary_figure(self):
        fig, ax = plt.subplots(1, 2, figsize=(10, 5))
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == self.mode], ax=ax[0])
        sns.countplot(x=self.name, data=self.df[self.df["mode"] == Mode.CAR], ax=ax[1])
        ax[0].set_title("Whether a trip had a valid rerouted\ntrip for canonical transit trips")
        ax[1].set_title("Whether a trip had a valid rerouted\ntrip for canonical car trips")
        
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