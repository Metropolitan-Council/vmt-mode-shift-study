import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

from steps.parent_classes import CategoricalStep
from steps.enums import *
from steps.figure_lib import *
from util import bigger_markdown

import inspect

import sys
sys.path.append("...")
from settings import handler

class WalkPurposeStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df, "likely_walk_purpose", Mode.WALK, Phase.PROBABLE)
        
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
        fig, ax = plot_multi_barplot(self.df[(self.df["purpose_cleaned"] != "Missing") & (self.df["mode"] == self.mode)], "purpose_cleaned", "mode", figsize=(20, 5))
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
        ax.set_title("Count plot of the cleaneddestination purposes in the TBI data, segmented by mode")
        
        return fig, ax
    
    def apply_step(self):
        super().apply_step(~self.df[self.name])
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""Some trip purposes cannot be switched from modes that facilitate them better--e.g., car for shopping trips. As such, we will consider any car trip that involves escorting someone or shopping to be less likely to switch to an alternative mode by default--this can be configured in the config.""")
        
        # summary figure
        res.append("""Placeholder""")
        
        # summary statistics
        res.append("Placeholder")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
    def show_step_streamlit(self):
        text = self.get_text()
    
        bigger_markdown(text[0])
        st.text("")
        
        bigger_markdown("Below, we can see the distribution of all the cleaned purposes in the TBI data. As can be seen, the most popular trip purposes are the fundamental, primary ones like going to work or returnign home.")
        
        fig, ax = plt.subplots(figsize=(20, 5))
        sns.countplot(x="purpose_cleaned", data=self.df[self.df["purpose_cleaned"] != "Missing"], ax=ax)
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
        ax.set_title("Count plot of the cleaned destination purposes in the TBI data")
        st.pyplot(fig)
        
        slots = []
        
        for section in text[1:]:
            bigger_markdown(section)
            temp = st.empty()
            slots.append(temp)
            
        slots[0].pyplot(self.get_summary_figure()[0])
        slots[1].dataframe(self.get_summary_statistics())
        slots[2].plotly_chart(self.get_map())
        
class BikePurposeStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df, "likely_bike_purpose", Mode.BIKE, Phase.PROBABLE)
        
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
        fig, ax = plot_multi_barplot(self.df[(self.df["purpose_cleaned"] != "Missing") & (self.df["mode"] == self.mode)], "purpose_cleaned", "mode", figsize=(20, 5))
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
        ax.set_title("Count plot of the cleaned destination purposes in the TBI data, segmented by mode")
        
        return fig, ax
    
    def apply_step(self):
        super().apply_step(~self.df[self.name])
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""Some trip purposes cannot be switched from modes that facilitate them better--e.g., car for shopping trips. As such, we will consider any car trip that involves escorting someone or shopping to be less likely to switch to an alternative mode by default--this can be configured in the config.""")
        
        # summary figure
        res.append("""Placeholder""")
        
        # summary statistics
        res.append("Placeholder")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
    def show_step_streamlit(self):
        text = self.get_text()
    
        bigger_markdown(text[0])
        st.text("")
        
        bigger_markdown("Below, we can see the distribution of all the cleaned purposes in the TBI data. As can be seen, the most popular trip purposes are the fundamental, primary ones like going to work or returnign home.")
        
        fig, ax = plt.subplots(figsize=(20, 5))
        sns.countplot(x="purpose_cleaned", data=self.df[self.df["purpose_cleaned"] != "Missing"], ax=ax)
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
        ax.set_title("Count plot of the cleaned destination purposes in the TBI data")
        st.pyplot(fig)
        
        slots = []
        
        for section in text[1:]:
            bigger_markdown(section)
            temp = st.empty()
            slots.append(temp)
            
        slots[0].pyplot(self.get_summary_figure()[0])
        slots[1].dataframe(self.get_summary_statistics())
        slots[2].plotly_chart(self.get_map())
        
class TransitPurposeStep(CategoricalStep):
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df, "likely_transit_purpose", Mode.TRANSIT, Phase.PROBABLE)
        
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
        fig, ax = plot_multi_barplot(self.df[(self.df["purpose_cleaned"] != "Missing") & (self.df["mode"] == self.mode)], "purpose_cleaned", "mode", figsize=(20, 5))
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
        ax.set_title("Count plot of the cleaneddestination purposes in the TBI data, segmented by mode")
        
        return fig, ax
    
    def apply_step(self):
        super().apply_step(~self.df[self.name])
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""Some trip purposes cannot be switched from modes that facilitate them better--e.g., car for shopping trips. As such, we will consider any car trip that involves escorting someone or shopping to be less likely to switch to an alternative mode by default--this can be configured in the config.""")
        
        # summary figure
        res.append("""Placeholder""")
        
        # summary statistics
        res.append("Placeholder")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
    def show_step_streamlit(self):
        text = self.get_text()
    
        bigger_markdown(text[0])
        st.text("")
        
        bigger_markdown("Below, we can see the distribution of all the cleaned purposes in the TBI data. As can be seen, the most popular trip purposes are the fundamental, primary ones like going to work or returnign home.")
        
        fig, ax = plt.subplots(figsize=(20, 5))
        sns.countplot(x="purpose_cleaned", data=self.df[self.df["purpose_cleaned"] != "Missing"], ax=ax)
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
        ax.set_title("Count plot of the cleaned destination purposes in the TBI data")
        st.pyplot(fig)
        
        slots = []
        
        for section in text[1:]:
            bigger_markdown(section)
            temp = st.empty()
            slots.append(temp)
            
        slots[0].pyplot(self.get_summary_figure()[0])
        slots[1].dataframe(self.get_summary_statistics())
        slots[2].plotly_chart(self.get_map())