import pandas as pd
import geopandas as gpd
import plotly.express as px
import streamlit as st
import re
from scipy import stats
import logging

from matplotlib.colors import LinearSegmentedColormap
from util import bigger_markdown

rg = LinearSegmentedColormap.from_list('rg',["r", "w", "g"], N=256) 
rg.set_bad(color="grey")

from .enums import *

import sys
sys.path.append("..")
from settings import get_communities
    
class BaseStep:
    
    def __init__(self, df: pd.DataFrame, name: str, mode: Mode, overall_step: Phase):
        self.df = df
        self.name = name
        self.mode = mode
        self.overall_step = overall_step
        self.prev = pd.to_numeric(self.df[f"{self.overall_step}_{mode}_shift"]).copy()
        
        self.previous_run = None
        
    def get_summary_statistics(self):
        raise NotImplementedError("Please implement this function")
    
    def get_summary_figure(self):
        raise NotImplementedError("Please implement this function")
    
    def apply_step(self, expression: pd.Series) -> None:
        self.df.loc[:, f"{self.overall_step}_{self.mode}_shift"] = self.prev
        
        self.df.loc[:, self.name] = True
        self.df.loc[expression, self.name] = False
        self.df.loc[expression, f"{self.overall_step}_{self.mode}_shift"] = False
    
    def get_step_statistics(self):
        abs_car_percent = len(self.df[(self.df['mode']==Mode.CAR) & (self.df[self.name])]) / len(self.df[self.df['mode']==Mode.CAR])
        abs_vmt_percent = self.df[(self.df['mode']==Mode.CAR) & (self.df[self.name])]["vmt"].sum() / self.df[self.df['mode']==Mode.CAR]["vmt"].sum()
        
        percent_shifts_before = len(self.df[(self.df['mode']==Mode.CAR) & (self.prev)]) / len(self.df[self.df['mode']==Mode.CAR]) * 100
        percent_shifts_after = len(self.df[(self.df['mode']==Mode.CAR) & (self.df[f'{self.overall_step}_{self.mode}_shift'])]) / len(self.df[self.df['mode']==Mode.CAR]) * 100
        
        prev_vmt = self.df[(self.df["mode"] == Mode.CAR) & (self.prev)]["vmt"].sum()
        after_vmt = self.df[(self.df["mode"] == Mode.CAR) & self.df[f"{self.overall_step}_{self.mode}_shift"]]["vmt"].sum()
        
        return ((percent_shifts_before, percent_shifts_after), (prev_vmt, after_vmt), (abs_car_percent, abs_vmt_percent))
    
    def get_map(self):
        temp = self.df[(self.df["community"] != "na") & (self.df["mode"]==Mode.CAR)][["community", self.name]]
        
        values = (temp.groupby("community")[self.name].mean()).fillna(0)
        communities = get_communities()
        communities[f"Proportion of people that can shift {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}"] = values
        # UTM 15-n, crs 26915
        fig = px.choropleth_mapbox(communities, 
                            geojson=communities.geometry, 
                            locations=communities.index, 
                            color=f"Proportion of people that can shift {'feasibly' if st.session_state.phase == Phase.FEASIBLE else 'with likelihood'}", color_continuous_scale="viridis_r", 
                            range_color=(0, 1),
                            mapbox_style="carto-positron",
                            center={"lat": 44.9778, "lon": -93.2650},
                            opacity=0.8,
                            title="Choropleth of proportion of people that can shift from car for this criteria"  # doesnt work
        )
        fig.update_layout(margin=dict(l=0, r=0, b=0, t=0),
                  width=900, 
                  height=500
        )
        fig.update_geos(fitbounds="locations", visible=False)
        return fig
    
    def disable(self) -> None:
        self.df.loc[:, f"{self.overall_step}_{self.mode}_shift"] = self.prev
        self.df.loc[:, self.name] = True
        self.previous_run = None
    
    def __repr__(self) -> str:
        return "Running the step with " + self.name + " as a criteria for shifts to " + self.mode
    
    def get_text(self) -> list[str]:
        # these are interlaced between the figures in each step
        # there should be # figures + 2 text blocks to return for each step typically (intro, n figure explanations, ending conclusion)
        # this builds the conclusion and the generic map snippet
        stats = self.get_step_statistics()
        total_vmt = self.df[(self.df["mode"] == Mode.CAR)]["vmt"].sum()
        if self.overall_step == Phase.FEASIBLE:
            return [
                f"Here, the map of the proportion of car trips in each community area that meet this mode's specified criteria for shifting to {self.mode} can be seen. There are a few transparent/white areas; these are the areas with no people to report.",
                f"""Before this step, <strong>{stats[0][0]:.2f}%</strong> of trips could shift to {self.mode} {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}, and after this step, <strong>{stats[0][1]:.2f}%</strong> of trips could shift to {self.mode} {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}.
                
                Additionally, before this step, <strong>{stats[1][0] / total_vmt * 100:.2f}%</strong> of VMT could be mitigated with shifts to {self.mode}, and after this step, <strong>{stats[1][1] / total_vmt * 100:.2f}%</strong> of VMT could be mitigated with shifts to {self.mode}.
                
                Overall, independent of other steps, <strong>{stats[2][0] * 100:.2f}</strong>% of all car trips and <strong>{stats[2][1] * 100:.2f}</strong>% of VMT can satisfy this constraint."""
            ]
        elif self.overall_step == Phase.PROBABLE:
            return [
                f"Here, the map of the proportion of car trips in each community area that meet this mode's specified criteria for shifting to {self.mode} can be seen. There are a few transparent/white areas; these are the areas with no people to report.",
                f"""Before this step, <strong>{stats[0][0]:.2f}%</strong> of feasible trips could shift to {self.mode} {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}, and after this step, <strong>{stats[0][1]:.2f}%</strong> of feasible trips could shift to {self.mode} {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}.
                
                Additionally, before this step, <strong>{stats[1][0] / total_vmt * 100:.2f}%</strong> of feasible trip VMT could be mitigated with shifts to {self.mode}, and after this step, <strong>{stats[1][1] / total_vmt * 100:.2f}%</strong> of feasible trip VMT could be mitigated with shifts to {self.mode}.
                
                For absolute statistics, before this step, <strong>{stats[0][0] * st.session_state.feasible_pct:.2f}%</strong> of all trips could shift to {self.mode} {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}, and after this step, <strong>{stats[0][1] * st.session_state.feasible_pct:.2f}%</strong> of all trips could shift to {self.mode} {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}. 
                
                Furthermore, before this step, <strong>{stats[1][0] / total_vmt * 100 * st.session_state.feasible_pct:.2f}%</strong> of feasible trip VMT could be mitigated with shifts to {self.mode}, and after this step, <strong>{stats[1][1] / total_vmt * 100 * st.session_state.feasible_pct:.2f}%</strong> of feasible trip VMT could be mitigated with shifts to {self.mode}.
                
                Overall, independent of other steps, <strong>{stats[2][0] * 100:.2f}</strong>% of all car trips and <strong>{stats[2][1] * 100:.2f}</strong>% of VMT can satisfy this constraint."""
            ]
        else:
            logging.exception(f"Something went wrong with the overall step enum: {self.overall_step}")
            raise RuntimeError("Something went wrong with the overall step enum")
        
    def get_name(self) -> str:
        # this is a bit hacky, but feasible distance steps are called _dist internally,
        # convert this to distance in the UI
        return re.sub(r"(?<=\b)dist$", "distance", self.name.replace("_", " ")).title()
    
    def get_cutoff(self) -> float:
        raise NotImplementedError("Please implement this function")
    
    def is_continuous(self):
        raise NotImplementedError("Please implement this function")
    
    def show_step_streamlit(self):
        text = self.get_text()
    
        bigger_markdown(text[0])
        st.text("")
        
        slots = []
        
        for section in text[1:]:
            bigger_markdown(section)
            temp = st.empty()
            slots.append(temp)
        
        fig = self.get_summary_figure()
        if type(fig) == tuple:  # normal matplotlib fig, ax
            slots[0].pyplot(fig[0])
        else:  # plotly chart
            slots[0].plotly_chart(fig)
            
        slots[1].markdown(self.get_summary_statistics().to_html(escape=False) + "<br>", unsafe_allow_html=True)
        slots[2].plotly_chart(self.get_map())
        
    def get_previous_run(self):
        return self.previous_run
    
    def get_mode(self) -> Mode:
        return self.mode
    
    def get_desc(self) -> str:
        raise NotImplementedError("Please implement this function")

class ContinuousStep(BaseStep):
    
    def __init__(self, df: pd.DataFrame, name: str, mode: Mode, cutoff: float, column_name: str, overall_step: Phase, units: str):
        super().__init__(df, name, mode, overall_step)
        self.cutoff = cutoff
        self.cutoff_mode = CutoffMode.PCT
        self.column_name = column_name
        self.units = units
        
    def get_desc(self) -> str:
        return f"This step applies a rule that if a trip has a value of <strong>{' '.join(self.get_name().split()[1:]).lower()}</strong> above the set cutoff (as a percentile or raw value), then it is considered {'infeasible' if self.overall_step == Phase.FEASIBLE else 'unlikely'} to shift to {self.mode}."
        
    def get_units(self) -> str:
        return self.units
        
    def apply_step(self, expression: pd.Series) -> None:
        logging.info(f"Running through the logic and visualization of continuous step {self.name}")
        self.previous_run = (self.cutoff, self.cutoff_mode)
        super().apply_step(expression)
        
    def get_cutoff_mode(self) -> CutoffMode:
        return self.cutoff_mode
        
    def set_cutoff_mode(self, new_mode: CutoffMode) -> None:
        self.cutoff_mode = new_mode
        
    def set_cutoff(self, new_cutoff) -> None:
        self.cutoff = new_cutoff
        
    def is_continuous(self):
        return True
    
    def disable(self) -> None:
        super().disable()
        self.cutoff = -1
        
    def get_cutoff(self) -> float:
        return self.cutoff
    
    def get_cutoff_equivalent(self):
        if self.cutoff_mode == CutoffMode.PCT:
            return self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff)
        elif self.cutoff_mode == CutoffMode.RAW:
            return stats.percentileofscore(self.df[self.df["mode"] == self.mode][self.column_name], self.cutoff) / 100
        else:
            raise RuntimeError("something went wrong with the cutoff mode enum")
        
    def get_cutoff_pct(self) -> float:
        if self.cutoff == -1:
            return 1
        if self.cutoff_mode == CutoffMode.PCT:
            return self.cutoff
        elif self.cutoff_mode == CutoffMode.RAW:
            return stats.percentileofscore(self.df[self.df["mode"] == self.mode][self.column_name], self.cutoff) / 100
        else:
            raise RuntimeError("something went wrong with the cutfof mode enum")
        
    def get_extrema(self) -> tuple:
        return self.df[self.df["mode"] == self.mode][self.column_name].quantile(0.01), self.df[self.df["mode"] == self.mode][self.column_name].quantile(0.99)

class CategoricalStep(BaseStep):
    
    def apply_step(self, expression: pd.Series) -> None:
        logging.info(f"Running through the logic and visualization of categorical step {self.name}")
        self.previous_run = 1
        self.df.loc[:, f"{self.overall_step}_{self.mode}_shift"] = self.prev
        self.df.loc[expression, f"{self.overall_step}_{self.mode}_shift"] = False
        
    def is_continuous(self):
        return False
        
    def get_cutoff(self) -> float:
        return -1
    
    def get_desc(self) -> str:
        return f"This step applies a categorical rule where if a trip satisfies the <string>{' '.join(self.get_name().split()[1:]).lower()}</strong> property, it is considered {'feasible' if self.overall_step == Phase.FEASIBLE else 'likely'} to shift to {self.mode}; otherwise, it is considered {'infeasible' if self.overall_step == Phase.FEASIBLE else 'unlikely'}."
    