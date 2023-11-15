import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import re
from scipy import stats
import logging
from typing import List, Dict
from abc import ABC, abstractstaticmethod, abstractmethod

from matplotlib.colors import LinearSegmentedColormap
from util import bigger_markdown

rg = LinearSegmentedColormap.from_list('rg',["r", "w", "g"], N=256) 
rg.set_bad(color="grey")

from .enums import *

import sys
sys.path.append("..")
from settings import get_communities, handler
    
class BaseStep(ABC):
    """
    This class serves as the base class for all other steps. It contains instance variables/methods shared by all children.
    """
    
    def __init__(self, df: pd.DataFrame, name: str, mode: Mode, overall_step: Phase):
        """Initializer of the base class.

        Args:
            df (pd.DataFrame): alias to internal dataframe of tool
            name (str): name of the step
            mode (Mode): mode the step applies to
            overall_step (Phase): the overall phase/step the step applies to
        """
        self.df = df
        self.name = name
        self.mode = mode
        self.overall_step = overall_step
            
        # snapshot of what the mode shift column looked like before this step was ran
        # used to allow the disabling of steps and the reversion of the dataframe back to what it was originally
        self.prev = pd.to_numeric(self.df[f"{self.overall_step}_{mode}_shift"]).copy()
        
        self.previous_run = None  # the summary statistics of the last run of the program
        
    
    @abstractmethod
    def get_summary_statistics(self):
        """
        This function returns the the summary statistics of the column this step applies to.
        """
        # abstract function -- not defined for base class
        raise NotImplementedError("This function needs to be overwritten")
    
    @abstractmethod
    def get_summary_figure(self):
        """
        This function returns a representative summary figure for the current step.
        """
        # abstract function -- not defined for base class
        raise NotImplementedError("This function needs to be overwritten")
    
    def apply_step(self, expression: pd.Series) -> None:
        """
        This function applies the step, given an expression relating to the step to evaluate.

        Args:
            expression (pd.Series): A boolean column such that if a row is True, it is unable to shift feasibly/with likelihood
        """
        # reset column to the snapshot taken before the step
        self.df.loc[:, f"{self.overall_step}_{self.mode}_shift"] = self.prev
        
        # reset this step's column, apply it, and update the mode shift column accordingly
        self.df.loc[:, self.name] = True
        self.df.loc[expression, self.name] = False
        self.df.loc[expression, f"{self.overall_step}_{self.mode}_shift"] = False
    
    def get_step_statistics(self):
        """
        This function gets the summary statistics for the step itself -- usually % shifts/VMT before/after

        Returns:
            tuple: 3 2-tuples, the first being percent shift before/after, the second being vmt before/after, and the third absolute car/vmt that satisfy this constraint
        """
        # absolute car/vmt % this step applies
        abs_car_percent = self.df[(self.df['mode']==Mode.CAR) & (self.df[self.name])]["vehicle_trips"].sum() / self.df[self.df['mode']==Mode.CAR]["vehicle_trips"].sum()
        abs_vmt_percent = self.df[(self.df['mode']==Mode.CAR) & (self.df[self.name])]["vmt"].sum() / self.df[self.df['mode']==Mode.CAR]["vmt"].sum()
        
        # % feasible/likely shifts before/after this step
        percent_shifts_before = self.df[(self.df['mode']==Mode.CAR) & (self.prev)]["vehicle_trips"].sum() / self.df[self.df['mode']==Mode.CAR]["vehicle_trips"].sum() * 100
        percent_shifts_after = self.df[(self.df['mode']==Mode.CAR) & (self.df[f'{self.overall_step}_{self.mode}_shift'])]["vehicle_trips"].sum() / self.df[self.df['mode']==Mode.CAR]["vehicle_trips"].sum() * 100
        
        # VMT before/after this step
        prev_vmt = self.df[(self.df["mode"] == Mode.CAR) & (self.prev)]["vmt"].sum()
        after_vmt = self.df[(self.df["mode"] == Mode.CAR) & self.df[f"{self.overall_step}_{self.mode}_shift"]]["vmt"].sum()
        
        return ((percent_shifts_before, percent_shifts_after), (prev_vmt, after_vmt), (abs_car_percent, abs_vmt_percent))
    
    def get_map(self) -> go.Figure:
        """
        This function returns a choropleth of CTUs, where the color corresponds to the proportion of people in the CTU that can shift according to this indicator.

        Returns:
            go.Figure: A plotly choropleth map
        """
        # get a view of df with na communities filtered out and only car trips and with only CTU and the name of the step's column as columns
        temp = self.df[(self.df["CTU"] != "na") & (self.df["mode"]==Mode.CAR)][["CTU", self.name]]
        
        # get communities and create a dummy column in it as the proportion of people in each CTU that can shift
        values = (temp.groupby("CTU")[self.name].mean()).fillna(0)
        communities = get_communities()
        communities[f"Proportion of people that can shift {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}"] = values
        
        # EPSG 4326; create choropleth
        fig = px.choropleth_mapbox(communities, 
                            geojson=communities.geometry, 
                            locations=communities.index, 
                            color=f"Proportion of people that can shift {'feasibly' if st.session_state.phase == Phase.FEASIBLE else 'with likelihood'}", color_continuous_scale="viridis_r", 
                            range_color=(0, 1),
                            mapbox_style="carto-positron",
                            center={"lat": 44.9778, "lon": -93.2650},
                            opacity=0.8
        )
        
        # make more aesthetic
        fig.update_layout(margin=dict(l=0, r=0, b=0, t=40),
                  title=dict(
                      text="Choropleth of proportion of people that can shift from car for this criteria",
                      x=0.5,
                      y=0.98,
                      xanchor='center',
                      font=dict(size=18)
                  ),
                  width=900, 
                  height=500
        )
        
        # zoom in accordingly
        fig.update_geos(fitbounds="locations", visible=False)
        
        return fig
    
    def disable(self) -> None:
        """
        This function disables the current step. 
        """
        # reset overall mode shift column to snapshot
        self.df.loc[:, f"{self.overall_step}_{self.mode}_shift"] = self.prev
        
        # reset step column name & previous run
        self.df.loc[:, self.name] = True
        self.previous_run = None
    
    def __repr__(self) -> str:
        """This function returns the string representation of the step

        Returns:
            str: A description of what the class does
        """
        return "Running the step with " + self.name + " as a criteria for shifts to " + self.mode
    
    def get_text(self) -> List[str]:
        """
        This function returns a list of strings that can be used to build up a narrative about this step. Usually contains intro, analysis of summary
        statistics, and presentation/analysis of results. As a raw string, is meant for markdown.
        
        Returns:
            list[str]: A list of relevant strings
        """
        # these are interlaced between the figures in each step
        # there should be # figures + 2 text blocks to return for each step typically (intro, n figure explanations, ending conclusion)
        # this builds the conclusion and the generic map snippet
        stats = self.get_step_statistics()
        total_vmt = self.df[(self.df["mode"] == Mode.CAR)]["vmt"].sum()
        if self.overall_step == Phase.FEASIBLE:
            return [
                f"Here, the map of the proportion of car trips in each CTU area that meet this mode's specified criteria for shifting to {self.mode} can be seen. There are a few transparent/white areas; these are the areas with no people to report.",
                f"""Before this step, <strong>{stats[0][0]:.1f}%</strong> of trips could shift to {self.mode} {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}, and after this step, <strong>{stats[0][1]:.1f}%</strong> of trips could shift to {self.mode} {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}.
                
                Additionally, before this step, <strong>{stats[1][0] / total_vmt * 100:.1f}%</strong> of VMT could be mitigated with shifts to {self.mode}, and after this step, <strong>{stats[1][1] / total_vmt * 100:.1f}%</strong> of VMT could be mitigated with shifts to {self.mode}.
                
                Overall, independent of other steps, <strong>{stats[2][0] * 100:.1f}</strong>% of all car trips and <strong>{stats[2][1] * 100:.1f}</strong>% of VMT can satisfy this constraint."""
            ]
        elif self.overall_step == Phase.PROBABLE:
            return [
                f"Here, the map of the proportion of car trips in each CTU area that meet this mode's specified criteria for shifting to {self.mode} can be seen. There are a few transparent/white areas; these are the areas with no people to report.",
                f"""Before this step, <strong>{stats[0][0]:.1f}%</strong> of feasible trips could shift to {self.mode} {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}, and after this step, <strong>{stats[0][1]:.1f}%</strong> of feasible trips could shift to {self.mode} {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}.
                
                Additionally, before this step, <strong>{stats[1][0] / total_vmt * 100:.1f}%</strong> of feasible trip VMT could be mitigated with shifts to {self.mode}, and after this step, <strong>{stats[1][1] / total_vmt * 100:.1f}%</strong> of feasible trip VMT could be mitigated with shifts to {self.mode}.
                
                For absolute statistics, before this step, <strong>{stats[0][0] * st.session_state.feasible_pct:.1f}%</strong> of all trips could shift to {self.mode} {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}, and after this step, <strong>{stats[0][1] * st.session_state.feasible_pct:.1f}%</strong> of all trips could shift to {self.mode} {'feasibly' if self.overall_step == Phase.FEASIBLE else 'with likelihood'}. 
                
                Furthermore, before this step, <strong>{stats[1][0] / total_vmt * 100 * st.session_state.feasible_pct:.1f}%</strong> of feasible trip VMT could be mitigated with shifts to {self.mode}, and after this step, <strong>{stats[1][1] / total_vmt * 100 * st.session_state.feasible_pct:.1f}%</strong> of feasible trip VMT could be mitigated with shifts to {self.mode}.
                
                Overall, independent of other steps, <strong>{stats[2][0] * 100:.1f}</strong>% of all car trips and <strong>{stats[2][1] * 100:.1f}</strong>% of VMT can satisfy this constraint."""
            ]
        else:
            logging.exception(f"Something went wrong with the overall step enum: {self.overall_step}")
            raise RuntimeError("Something went wrong with the overall step enum")
        
    def get_name(self) -> str:
        """
        This function returns the name of the step.

        Returns:
            str: The name of the step
        """
        # this is a bit hacky, but feasible distance steps are called _dist internally,
        # convert this to distance in the UI
        return re.sub(r"(?<=\b)dist$", "distance", self.name.replace("_", " ")).title()
    
    @abstractmethod
    def get_cutoff(self) -> float:
        """
        This function returns the cutoff of the step.
        """
        # abstract function
        raise NotImplementedError("This function needs to be overwritten")
    
    @abstractmethod
    def is_continuous(self):
        """
        This function returns whether this step is continuous or not
        """
        # abstract function
        raise NotImplementedError("This function needs to be overwritten")
    
    def show_step_streamlit(self):
        """
        This function shows this step in its entirety in streamlit ('s center, around the sidebar). This includes both the narrative text and the figures that have 
        been coded within this class
        """
        
        # get desired text
        text = self.get_text()
    
        # show text and add a break between it and everything else
        bigger_markdown(text[0])
        st.text("")
        
        # create slots to insert figures into between text
        slots = []
        
        # show text with slots between
        for section in text[1:]:
            bigger_markdown(section)
            temp = st.empty()
            slots.append(temp)
        
        # fill in the gaps between text with figures
        fig = self.get_summary_figure()
        if type(fig) == tuple:  # normal matplotlib fig, ax
            slots[0].pyplot(fig[0])
        else:  # plotly chart
            slots[0].plotly_chart(fig, use_container_width=True)
            
        slots[1].markdown(self.get_summary_statistics().to_html(escape=False) + "<br>", unsafe_allow_html=True)
        slots[2].plotly_chart(self.get_map(), use_container_width=True)
        
    def get_previous_run(self):
        """
        This function gets the summary statistics of the previous (&last) run of the step, in particular the cutoff and cutoff mode. 

        Returns:
            tuple: (cutoff: float, cutoff_mode: CutofFMode)
        """
        return self.previous_run
    
    @staticmethod
    @abstractmethod
    def get_mode() -> Mode:
        """
        This function returns the mode this step applies to.

        Returns:
            Mode: the mode this function applies to
        """
        raise NotImplementedError("This function needs to be overwritten")
    
    @abstractmethod
    def get_desc(self) -> str:
        """
        This function gives a short blurb about the step to be shown in the pre-running stages.
        """
        # abstract function
        raise NotImplementedError("This function needs to be overwritten")
    
    def create_step_col(self, inputs: Dict[str, str], col_name: str):
        """
        This function does the overall setup for creating the input column for the current step, including validating
        the input fields and the target column name.
        
        Args:
            inputs (dict): a mapping of the column concepts used in this step to the associated column in the dataframe
        """
        self.validate_inputs(inputs, col_name)
        
        processed_inputs = self.process_inputs({key: self.df[val] for key, val in inputs.items()})
        
        if type(processed_inputs) == pd.DataFrame or (type(processed_inputs) == pd.Series and len(processed_inputs) != len(self.df)):
            raise RuntimeError("Something went wrong with input processing")
        
        if type(processed_inputs) == pd.Series:
            self.df[col_name] = processed_inputs.values
        else:
            self.df[col_name] = processed_inputs
        
    @staticmethod
    @abstractmethod
    def process_inputs(inputs: Dict[str, pd.Series]) -> pd.Series:
        """
        This function implements the actual logic for creating the input column for the current step. 
        
        Args:
            inputs (dict): a dictionary of the concepts this step uses to their associated dataframe columns (series)

        This function needs to be overwritten, as the exact logic of processing inputs depends on the step.
        """
        raise NotImplementedError("This function needs to be overwritten")

    def validate_inputs(self, inputs: Dict[str, str], col_name: str):
        """This function validates that this step's process of creating the column that will be used is valid--i.e., it won't cause a downstream error.
        """
        scenario_cols = set()
        def get_scenario_cols(curr):
            for key in curr.keys():
                if key == "mappings" and type(curr[key]) == dict:
                    scenario_cols.update(curr[key].keys())
                elif type(curr[key]) == dict:
                    get_scenario_cols(curr[key])
                    
        get_scenario_cols(handler["scenarios"])

        for field in inputs.values():
            if field not in handler["mappings"].keys() and field not in scenario_cols:
                raise RuntimeError("Specified mapping does not reference a valid input column of the data")
            
        if col_name in handler["mappings"].keys() or col_name in scenario_cols:
            raise RuntimeError("Target column will overwrite an input column of the data")
    

class ContinuousStep(BaseStep):
    """
    This class is one part of the first level of specialization of the base class, inheriting from it. It is the parent for all steps that are continuous in nature.
    """
    
    def __init__(self, df: pd.DataFrame, name: str, inputs: Dict[str, str], mode: Mode, cutoff: float, column_name: str, overall_step: Phase, units: str):
        """
        Initializes the continuous step base class

        Args:
            df (pd.DataFrame): alias to the dataframe for information retrieval
            name (str): name of the step   
            mode (Mode): mode the step applies to
            cutoff (float): the numerical cutoff to begin with
            column_name (str): the name of the column this step utilizes
            overall_step (Phase): the overall step this step pertains to (feasible/probable)
            units (str): the units of raw cutoffs of this step
        """
        super().__init__(df, name, mode, overall_step)  # call the parent constructor for these
        self.cutoff = cutoff
        self.cutoff_mode = CutoffMode.PCT
        self.column_name = column_name
        self.units = units
        
        super().create_step_col(inputs, self.column_name)
    
    @staticmethod
    def process_inputs(inputs: Dict[str, pd.Series]) -> pd.Series:
        """
        This function implements the actual logic for creating the input column for the current step. NOTE: in the logic to create this
        input column, only use the columns described in the config.yaml.

        This particular specialization leverages the fact that for the majority of continuous steps, only one input is needed, which is exactly the column
        used for the step. Therefore, we can just return that input, assuming there is no processing that needs to be done (e.g., scaling).
        
        However, this should be overwritten if any preprocessing is needed on the raw input column, and this needs to be overwritten
        if there are >1 inputs.
        """
        if (len(inputs) == 1):
            return list(inputs.values())[0]
        
        
        raise NotImplementedError("The input is nontrivial, and this function needs to be implemented in the specialized class.")
        
    def get_desc(self) -> str:
        # gives brief description of what the step does
        return f"This step applies a rule that if a trip has a value of <strong>{' '.join(self.get_name().split()[1:]).lower()}</strong> above the set cutoff (as a percentile or raw value), then it is considered {'infeasible' if self.overall_step == Phase.FEASIBLE else 'unlikely'} to shift to {self.mode}."
        
    def get_units(self) -> str:
        """
        This function returns the units of the cutoffs of this step.

        Returns:
            str: units
        """
        return self.units
        
    def apply_step(self, expression: pd.Series) -> None:
        logging.info(f"Running through the logic and visualization of continuous step {self.name}")
        
        # save the previous run here (with cutoffs), then apply the expression like previously
        self.previous_run = (self.cutoff, self.cutoff_mode, self.get_cutoff_equivalent(), self.get_cutoff_pct())
        super().apply_step(expression)
        
    def get_cutoff_mode(self) -> CutoffMode:
        """
        This function returns the cutoff mode of this step.

        Returns:
            CutoffMode: the cutoff mode of this step
        """
        return self.cutoff_mode
        
    def set_cutoff_mode(self, new_mode: CutoffMode) -> None:
        """
        This function allows the setting of the cutoffmode of this step.

        Args:
            new_mode (CutoffMode): the new mode to set the cutoff mode of this step to
        """
        self.cutoff_mode = new_mode
        
    def set_cutoff(self, new_cutoff: float) -> None:
        """
        This function allows the setting of the cutoff of this step.

        Args:
            new_mode (float): the new cutoff to set the cutoff of this step to
        """
        self.cutoff = new_cutoff
        
    def is_continuous(self):
        # this is necessarily continuous
        return True
    
    def disable(self) -> None:
        # disable like normal but then set cutoff to -1 to signify this
        super().disable()
        self.cutoff = -1
        
    def get_cutoff(self) -> float:
        """
        This function returns the cutoff of this step.

        Returns:
            float: the cutoff of this step
        """
        return self.cutoff
    
    def get_cutoff_equivalent(self) -> float:
        """
        This function gets the cutoff equivalent of the current cutoff -- e.g., if the current cutoff is a percentile, it would give the equivalent
        of that percentile in terms of raw numbers/units.

        Returns:
            float: cutoff in the cutoff mode opposite to the step's current cutoff mode
        """
        # to get the raw # corresponding to a percentile, use quantile
        if self.cutoff_mode == CutoffMode.PCT:
            return self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff)
        # to convert raw score to percentile, can use scipy
        elif self.cutoff_mode == CutoffMode.RAW:
            return stats.percentileofscore(self.df[self.df["mode"] == self.mode][self.column_name], self.cutoff) / 100
        else:
            raise RuntimeError("something went wrong with the cutoff mode enum")
        
    def get_cutoff_pct(self) -> float:
        """
        This function always returns the cutoff of the step in percentile (i..e, if the step is in raw mode, returns the corresponding percentile).

        Returns:
            float: Percentile cutoff (possibly equivalency) of this step
        """
        if self.cutoff == -1:
            return 1
        # if it is already a percentile, do nothing
        if self.cutoff_mode == CutoffMode.PCT:
            return self.cutoff
        # otherwise, use scipy to convert raw to percentile
        elif self.cutoff_mode == CutoffMode.RAW:
            return stats.percentileofscore(self.df[self.df["mode"] == self.mode][self.column_name], self.cutoff) / 100
        else:
            raise RuntimeError("something went wrong with the cutfof mode enum")
        
    def get_extrema(self) -> tuple:
        """
        This function gets the extrema of the raw range of the steps, defined by the 1st percenitle to the 99th percentile of this step's column.

        Returns:
            tuple: (min, max)
        """
        return self.df[self.df["mode"] == self.mode][self.column_name].quantile(0.01), self.df[self.df["mode"] == self.mode][self.column_name].quantile(0.99)

class CategoricalStep(BaseStep):
    
    def __init__(self, df: pd.DataFrame, name: str, inputs: Dict[str, str], mode: Mode, phase: Phase):
        super().__init__(df, name, mode, phase)
        
        super().create_step_col(inputs, self.name)
    
    def apply_step(self, expression: pd.Series) -> None:
        logging.info(f"Running through the logic and visualization of categorical step {self.name}")
        # overwrite parent apply_step completely
        # set previous run to 1 (no cutoffs) and apply the expression directly since this is a true/false thing
        # do this since calling the super will create a redundant column that matches directly to this step's internal column
        self.previous_run = 1
        self.df.loc[:, f"{self.overall_step}_{self.mode}_shift"] = self.prev
        self.df.loc[expression, f"{self.overall_step}_{self.mode}_shift"] = False
        
    def is_continuous(self):
        # categorical steps are never continuous
        return False
        
    def get_cutoff(self) -> float:
        # can just let cutoff of categorical steps be -1
        return -1
    
    def get_desc(self) -> str:
        # quick blurb of what this step does/how it works
        return f"This step applies a categorical rule where if a trip satisfies the <string>{' '.join(self.get_name().split()[1:]).lower()}</strong> property, it is considered {'feasible' if self.overall_step == Phase.FEASIBLE else 'likely'} to shift to {self.mode}; otherwise, it is considered {'infeasible' if self.overall_step == Phase.FEASIBLE else 'unlikely'}."
    