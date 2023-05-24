import pandas as pd
import geopandas as gpd
import plotly.express as px
import streamlit as st

from matplotlib.colors import LinearSegmentedColormap

rg = LinearSegmentedColormap.from_list('rg',["r", "w", "g"], N=256) 
rg.set_bad(color="grey")

from . mode_enum import Mode

import sys
sys.path.append("..")
from settings import get_communities
    
class BaseStep:
    
    def __init__(self, df: pd.DataFrame, name: str, mode: Mode):
        self.df = df
        self.name = name
        self.mode = mode
        self.prev = pd.to_numeric(self.df[f"feasible_{mode}_shift"]).copy()
        
    def get_summary_statistics(self):
        raise NotImplementedError("Please implement this function")
    
    def get_summary_figure(self):
        raise NotImplementedError("Please implement this function")
    
    def apply_step(self, expression: pd.Series) -> None:
        self.df.loc[:, f"feasible_{self.mode}_shift"] = self.prev
        
        self.df.loc[:, self.name] = True
        self.df.loc[expression, self.name] = False
        self.df.loc[expression, f"feasible_{self.mode}_shift"] = False
    
    def get_step_statistics(self):
        percent_shifts_before = len(self.df[(self.df['mode']==Mode.CAR) & (self.prev)]) / len(self.df[self.df['mode']==Mode.CAR]) * 100
        percent_shifts_after = len(self.df[(self.df['mode']==Mode.CAR) & (self.df[f'feasible_{self.mode}_shift'])]) / len(self.df[self.df['mode']==Mode.CAR]) * 100
        
        prev_vmt = self.df[(self.df["mode"] == Mode.CAR) & (self.prev)]["vmt"].sum()
        after_vmt = self.df[(self.df["mode"] == Mode.CAR) & self.df[f"feasible_{self.mode}_shift"]]["vmt"].sum()
        
        return ((percent_shifts_before, percent_shifts_after), (prev_vmt, after_vmt))
    
    def get_map(self):
        temp = self.df[self.df["community"] != -1][["community", self.name]]
        
        values = (temp.groupby("community")[self.name].mean()).fillna(0)
        communities = get_communities()
        communities["val"] = values
        fig = px.choropleth(communities, geojson=communities.geometry, locations=communities.index, color="val", color_continuous_scale=["red", "yellow", "green"], range_color=(0, 1))
        fig.update_layout(margin=dict(l=0, r=0, b=0, t=0),
                  width=900, 
                  height=500,
        )
        fig.update_geos(fitbounds="locations", visible=False)
        return fig
    
    def disable(self) -> None:
        self.df.loc[:, f"feasible_{self.mode}_shift"] = self.prev
        self.df.loc[:, self.name] = True
    
    def __repr__(self) -> str:
        return "Running the step with " + self.name + " as a criteria for shifts to " + self.mode
    
    def get_text(self) -> list[str]:
        # these are interlaced between the figures in each step
        # there should be # figures + 2 text blocks to return for each step typically (intro, n figure explanations, ending conclusion)
        # this builds the conclusion and the generic map snippet
        stats = self.get_step_statistics()
        total_vmt = self.df[(self.df["mode"] == Mode.CAR)]["vmt"].sum()
        return [
            f"Here, the map of the % of car trips in each community area that meet this mode's specified criteria for shifting to {self.mode} can be seen. There are a few transparent/white areas; these are the areas with no people to report.",
            f"""Before this step, **{stats[0][0]}%** of trips could shift to {self.mode} feasibly/with likelihood, and after this step, **{stats[0][1]}%** of trips could shift to {self.mode} feasibly/with likelihood.
            
            Additionally, before this step, **{stats[1][0] / total_vmt * 100}%** of VMT could be mitigated with shifts to {self.mode}, and after this step, **{stats[1][1] / total_vmt * 100}%** of VMT could be mitigated with shifts to {self.mode}."""
        ]
        
    def get_name(self) -> str:
        return self.name.replace("_", " ").title()
    
    def get_cutoff(self) -> float:
        return -1


class ContinuousStep(BaseStep):
    
    def __init__(self, df: pd.DataFrame, name: str, mode: Mode, cutoff: float, column_name: str):
        super().__init__(df, name, mode)
        self.cutoff = cutoff
        self.column_name = column_name
        
    def set_cutoff(self, new_cutoff: float) -> None:
        self.cutoff = new_cutoff
        
    def is_continuous(self):
        return True
    
    def disable(self) -> None:
        super().disable()
        self.cutoff = -1
        
    def get_cutoff(self) -> float:
        return self.cutoff
    
    def get_cutoff_numerical(self) -> float:
        return self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff)

class CategoricalStep(BaseStep):
    
    def apply_step(self, expression: pd.Series) -> None:
        self.df.loc[:, f"feasible_{self.mode}_shift"] = self.prev
        self.df.loc[expression, f"feasible_{self.mode}_shift"] = False
        
    def is_continuous(self):
        return False
        
    