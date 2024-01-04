import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import inspect
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict
from collections import defaultdict

import steps
from settings import handler, get_communities
from steps.enums import *
from util import get_cold_starts_df, stacked_shift_histogram, total_shift_histogram, get_summary_df, get_duration_diff_df, bigger_markdown, validate_input, create_scenario_input, in_scenario, create_base_step, create_scenario_step, show_previous_runs, create_sdf
import json
import logging

# do conditional imports based on whether we are in build mode
# keyring/initialization is not necessary in build mode amd breaks things
try:
    # from initialize import prepare_data, anonymize, add_scenarios
    import keyring
except ImportError as e:
    logging.error("Unable to import keyring/prepare_data; if this is occurring and the program is not in build mode, something is wrong")
    
    # only valid if in build mode 
    if not handler["build"]:
        logging.exception("Imports failed and program is not in build mode, something has gone wrong")
        raise e
except Exception as e:
    logging.exception(f"Something has gone wrong with the import logic: {e}")
    raise e
    
def run_all(phase: Phase) -> None:
    """
    This function is the helper for running all selected steps in a given phase.
    """
    
    raise NotImplementedError("Deprecated in favor of fast mode.")
    
    # setup df if not done yet
    if "df" not in st.session_state:
        setup_df()
        
    # setup the current phase's variables
    setup_vars(phase)

    # run through each selected step of the current phase
    if phase == Phase.FEASIBLE:
        for step in st.session_state.feasible_steps:
            curr: steps.parent_classes.BaseStep = getattr(st.session_state.overall_step, step)(
                st.session_state.df,
                handler[f"feasible_steps"][step]
            )
            curr.apply_step()
            st.session_state.step_class_dict[step] = curr
    elif phase == Phase.PROBABLE:
        for step in st.session_state.probable_steps:
            curr: steps.parent_classes.BaseStep = getattr(st.session_state.overall_step, step)(
                st.session_state.df,
                handler[f"probable_steps"][step]
            )
            curr.apply_step()
            st.session_state.step_class_dict[step] = curr
            
    # toggle summary screen and refresh streamlit
    st.session_state["summary_screen"] = True
    st.experimental_rerun()
        
def start_screen_feasible() -> None:
    """
    This function generates the start screen for the feasible phase.
    """
    
    # title
    st.title("Configure the feasible phase")
    
    # feasible vs. probable blurb
    bigger_markdown("The feasible phase involves steps that determine whether a trip can feasibly shift to a given mode or not. In contrast, the probable phase, which follows the feasible phase, places more restrictions on the already feasible trips to determine whether a trip can shift to a mode with likelihood.")
    
    st.markdown("***")
    
    # explanation for checkmarks
    bigger_markdown(inspect.cleandoc("""The checked steps will be able to be run in the visualization tool. There should be at least one step checked before beginning, but ideally, one step that applies to each mode should be checked for meaningful overall results. 
                
    At the left, clicking begin will start the in-depth tool with the selected steps, clicking begin with all steps checked will begin the in-depth tool with all the steps included regardless of the checked steps, and clicking run all will automatically run all the selected steps."""))
    
    # create feasible_steps session state array if not present as well as a scenarios dictionary
    if "feasible_steps" not in st.session_state:
        st.session_state["feasible_steps"] = []
        st.session_state["scenarios"] = {mode: "default" for mode in Mode.get_all()}
    
    # define all actions that can be done
    st.sidebar.header("Actions")
        
    # begin visualization tools with selected steps
    if st.sidebar.button("Begin"):
        logging.info("Beginning tool with selected steps")
        
        # setup variables, toggle start screen feasible off, and refresh
        if "phase" not in st.session_state or st.session_state.phase != Phase.FEASIBLE:
            setup_vars(Phase.FEASIBLE)
        st.session_state.start_screen_feasible = False
        st.experimental_rerun()
    
    # begin visualization with all steps selected by default
    if st.sidebar.button("Begin with all steps selected"):
        logging.info("Beginning tool with all steps")
        
        # set feasible steps to all defined feasible steps
        st.session_state["feasible_steps"] = list(handler["feasible_steps"])
        
        # setup variables/toggle start screen feasible off and refresh
        if "phase" not in st.session_state or st.session_state.phase != Phase.FEASIBLE:
            setup_vars(Phase.FEASIBLE)
        st.session_state.start_screen_feasible = False
        st.experimental_rerun()
        
    st.session_state.fast_mode = st.sidebar.checkbox("Fast rendering mode")
        
    # # run all selected steps automatically
    # if st.sidebar.button("Run all selected steps"):
    #     logging.info("Running through all steps automatically")
        
    #     # toggle start screen & call the run all function for feasible
    #     st.session_state.start_screen_feasible = False
    #     run_all(Phase.FEASIBLE)
        
    # create the multiselect to choose steps
    # NOTE: this can sometimes be buggy if you don't click off the multiselect before running it, as the session state sometimes takes a bit to fully respond to user input
    st.session_state["feasible_steps"] = st.multiselect("Choose the feasible steps to run", handler["feasible_steps"])
    
    st.markdown("***")
    # overriding this scenario approach to use separate files instead. 
    # create the scenario picker; scenarios are persisted throughout the entire application
    bigger_markdown("Choose the scenarios to run for each mode. Choosing 'default' will not run any scenarios for the mode.")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.session_state["scenarios"][Mode.CAR] = st.radio(
            "Choose the car scenario:", 
            [x for x in handler["scenarios"][Mode.CAR].keys()], 
            format_func=lambda x: f"{x}: {handler['scenarios'][Mode.CAR][x]['description']}"
        )
        
    with col2:
        st.session_state["scenarios"][Mode.WALK] = st.radio(
            "Choose the walk scenario:", 
            [x for x in handler["scenarios"][Mode.WALK].keys()], 
            format_func=lambda x: f"{x}: {handler['scenarios'][Mode.WALK][x]['description']}"
        )
        
    with col3:
        st.session_state["scenarios"][Mode.BIKE] = st.radio(
            "Choose the bike scenario:", 
            [x for x in handler["scenarios"][Mode.BIKE].keys()], 
            format_func=lambda x: f"{x}: {handler['scenarios'][Mode.BIKE][x]['description']}"
        )
        
    with col4:
        st.session_state["scenarios"][Mode.TRANSIT] = st.radio(
            "Choose the transit scenario:", 
            [x for x in handler["scenarios"][Mode.TRANSIT].keys()], 
            format_func=lambda x: f"{x}: {handler['scenarios'][Mode.TRANSIT][x]['description']}"
        )
    
def start_screen_probable() -> None:
    """
    This function generates the start screen for the probable step.
    """
    
    # title
    st.title("Configure the probable steps")
    
    # feasible vs. probable blurb
    bigger_markdown("The feasible phase involves steps that determine whether a trip can feasibly shift to a given mode or not. In contrast, the probable phase, which follows the feasible phase, places more restrictions on the already feasible trips to determine whether a trip can shift to a mode with likelihood.")
    
    st.markdown("***")
    
    # explanation of checkmarks
    bigger_markdown(inspect.cleandoc("""The checked steps will be able to be run in the visualization tool. There should be at least one step checked before beginning, but ideally, one step that applies to each mode should be checked for meaningful overall results. 
                
    At the left, clicking begin will start the in-depth tool with the selected steps, clicking begin with all steps checked will begin the in-depth tool with all the steps included regardless of the checked steps, and clicking run all will automatically run all the selected steps."""))
    
    # init probable steps array if not already present
    if "probable_steps" not in st.session_state:
        st.session_state["probable_steps"] = []
    
    # define all the possible actions you can do at this point
    st.sidebar.header("Actions")
        
    # begin with selected steps; setup probable variables & toggle off this start screen & refresh
    if st.sidebar.button("Begin"):
        logging.info("Beginning tool with selected steps")
        if "phase" not in st.session_state or st.session_state.phase != Phase.PROBABLE:
            setup_vars(Phase.PROBABLE)
        st.session_state.start_screen_probable = False
        st.experimental_rerun()
        
    # begin with all steps selected; set probable steps to all probable steps & toggle off this start screen & refresh
    if st.sidebar.button("Begin with all steps selected"):
        logging.info("Beginning tool with all steps")
        
        st.session_state["probable_steps"] = handler["probable_steps"]
        if "phase" not in st.session_state or st.session_state.phase != Phase.PROBABLE:
            setup_vars(Phase.PROBABLE)
        st.session_state.start_screen_probable = False
        st.experimental_rerun()
        
    # # run through all selected steps automatically
    # if st.sidebar.button("Run all selected steps"):
    #     logging.info("Running through all steps automatically")
        
    #     # toggle off this start screen & call the run all function with the probable phase
    #     st.session_state.start_screen_probable = False
    #     run_all(Phase.PROBABLE)
    
    st.session_state.fast_mode = st.sidebar.checkbox("Fast rendering mode")
        
    # create the multiselect to choose the probable steps to run
    # NOTE: like with feasible steps, this can also be buggy sometimes
    st.session_state["probable_steps"] = st.multiselect("Choose the probable steps to run", handler["probable_steps"])

def setup_df() -> None:
    """
    This function reads in/sets up the input dataframe for the visualization tool.
    """
    
    # if we are in build mode, turn off logging; otherwise, send logs to output/
    if handler["build"]:
        logger = logging.getLogger()
        logger.disabled = True
    else:
        logging.getLogger().setLevel("INFO")
        logging.basicConfig(filename="output/streamlit.log", filemode="w", format="%(name)s - %(levelname)s - %(message)s")
        
    # if we are not in build, get the drive data dir using keyring
    if not handler["build"]:
        drive_data_dir = keyring.get_password('msp', 'vmt_reduction_dir')
        
    # if we are forcing reinitialization and we are not in build mode, reinitialize - -disabled
    if False and handler["force_reinitialize"] and not handler["build"]:
        logging.info("Rebuilding data from raw inputs")
        
        # read in data & pipe it through the cleaning function
        raw = pd.read_csv(drive_data_dir + handler["input_tbi_file"], usecols=handler["keep_columns"])
        df = prepare_data(raw, drive_data_dir)
    # otherwise, we are not reinitialization -- read in precleaned files
    else:
        logging.info("Attempting to read in pre-cleaned data files")
        
        # try to read in file specified as saved_tbi_file (supporting parquet/csv)
        try:
            if handler["tbi_file_name"].split(".")[-1] == "parquet":
                logging.info("Reading in the specified parquet file")
                df = pd.read_parquet(handler["tbi_file_name"])
            elif handler["tbi_file_name"].split(".")[-1] == "csv":
                logging.info("Reading in the specified csv file")
                df = pd.read_csv(handler["tbi_file_name"])
            
        # if we cannot read the input, try rebuilding, but if we are in build mode, raise an exception
        except Exception as e:
            logging.info(f"Something has gone wrong reading in the pre-cleaned data files: {e}")
            # if handler["build"]:
            #     logging.exception("Unable to rebuild data in build mode")
            #     raise e
            # logging.info("Attempting to rebuild inputs manually from scratch")
            # raw = pd.read_csv(drive_data_dir + handler["input_tbi_file"], usecols=handler["keep_columns"])

            # df = prepare_data(raw, drive_data_dir)
            raise e
        
    # store the generated df into a session state variable
    logging.info("Setting up the data inputs has succeeded")
    logging.info("NOTE: if the input data is not up-to-date with the most recent initialization schema, it could cause downstream errors.")
    st.session_state["df"] = df
    
    # validate dataframe -- useful for changes to schema that requires rebuilding
    validate_input(df)

    return 0

def setup_vars(phase: Phase) -> None:
    """This function sets up the variables for the passed in phase.

    Args:
        phase (Phase): the phase whose variables should be set up
    """
    logging.info(f"Setting up variables for phase {phase}")
    
    # if we are in the probable phase, make df the subset of trips that can feasibly shift, according to the probable phase logic
    if phase == Phase.PROBABLE:
        st.session_state["df"] = st.session_state.df.loc[st.session_state.df["feasible_shift"], :].copy()
        st.session_state["sdf"] = st.session_state.sdf.loc[st.session_state.sdf["feasible_shift"], :].copy()

    # have a handy short-hand alias for the session state dataframe variable
    df: pd.DataFrame = st.session_state.df
    
    # everything is feasible/probable initially
    df[f'{phase}_{Mode.WALK}_shift'] = True
    df[f'{phase}_{Mode.BIKE}_shift'] = True
    df[f'{phase}_{Mode.TRANSIT}_shift'] = True
    df[f'{phase}_shift'] = True
    
    # helper boolean for whether there is some scenario selected
    # if so, we need to mirror the base pipeline in the scenarios
    st.session_state.have_scenarios = (len(set(st.session_state["scenarios"].values())) != 1)
    
    # change the current phase stored in session state
    st.session_state["phase"] = phase

    # try to setup some initial step/overall_step logic using the feasible/probable step list we are working with
    # if no steps were selected, indexing to 0 is impossible, and this raises an error
    try:
        if phase == Phase.FEASIBLE:
            st.session_state["step"] = st.session_state.option = st.session_state["feasible_steps"][0]
            st.session_state["overall_step"] = steps.feasible_steps
        elif phase == Phase.PROBABLE:
            st.session_state["step"] = st.session_state.option = st.session_state["probable_steps"][0]
            st.session_state["overall_step"] = steps.probable_steps
        else:
            logging.exception(f"Something went wrong with the phase enum: {st.session_state.overall_step}")
            raise RuntimeError("Something went wrong with the phase enum")
    except IndexError as e:
        logging.exception("no steps selected in the initial start page -- need to restart program")
        raise RuntimeError("No steps selected in initial start page -- refresh to restart the tool")
    
    # create a dictionary for storing initialized step class objects and store the first step within it already
    st.session_state["step_class_dict"] = dict()
    st.session_state["step_class_dict"][st.session_state.step] = getattr(st.session_state.overall_step, st.session_state.step)(
        st.session_state.df,
        handler[f"{phase}_steps"][st.session_state.step]
    )
    
    # if we have scenarios
    if st.session_state.have_scenarios:
        # make a copy of the main df for scenario purposes
        if phase != Phase.PROBABLE:
            # st.session_state["sdf"] = st.session_state["df"].copy()
            st.session_state["sdf"] = create_sdf(df, st.session_state.scenarios)
            
        else:
            st.session_state.sdf[f'{phase}_{Mode.WALK}_shift'] = True
            st.session_state.sdf[f'{phase}_{Mode.BIKE}_shift'] = True
            st.session_state.sdf[f'{phase}_{Mode.TRANSIT}_shift'] = True
            st.session_state.sdf[f'{phase}_shift'] = True
        
        # record down scenario classes in a dict
        st.session_state["step_class_scenario_dict"] = dict()
        st.session_state["step_class_scenario_dict"][st.session_state.step] = create_scenario_step(st.session_state.step)
    
    # store the current step class (as an alias to the stored one in the dictionary)
    # st.session_state["step_class"] = st.session_state["step_class_dict"][st.session_state.step]
    # turn off the summary screen (want to show the normal step screen right now)
    st.session_state["summary_screen"] = False
    
def show_final_summary(df: pd.DataFrame, step_class_dict: Dict[str, steps.BaseStep]) -> None:
    """
    This function generates the final summary for the visualization tool given a dataframe and a step class dict that the dataframe
    followed. 
    """
    # df.to_parquet(f"output/fdsa{label}.parquet")
            
    # calculate overall shift ability -- can shift to at least one mode
    df[f"{st.session_state.phase}_shift"] = (
        df[f"{st.session_state.phase}_transit_shift"] | 
        df[f"{st.session_state.phase}_walk_shift"] | 
        df[f"{st.session_state.phase}_bike_shift"]
    )
    
    # save the feasible pct for later use in probable step
    if st.session_state.phase == Phase.FEASIBLE:
        st.session_state["feasible_pct"] = df[(df[f'{st.session_state.phase}_shift']) & (df['mode'] == Mode.CAR)]['vehicle_trips'].sum() / df[df['mode'] == Mode.CAR]['vehicle_trips'].sum()
    
    # which adjective to use (depends on phase)
    adjective = 'feasibly' if st.session_state.phase == Phase.FEASIBLE else 'with likelihood'
    
    # summary just has some overall statistics
    st.title("Summary")
    
    # total trips is the # of car trips total
    total_trips = df[df["mode"] == Mode.CAR]["vehicle_trips"].sum()
    
    # tell the % of people that can shift to any mode and to individual modes
    bigger_markdown(f"Overall, <strong>{len(step_class_dict)}</strong> steps were run, and, accounting for these restrictions, <strong>{df[(df[f'{st.session_state.phase}_shift']) & (df['mode'] == Mode.CAR)]['vehicle_trips'].sum() / total_trips * 100:.1f}%</strong> of all trips could shift {adjective} from car to some non-car mode. When considering individual mode shifts, <strong>{df[(df[f'{st.session_state.phase}_transit_shift']) & (df['mode'] == Mode.CAR)]['vehicle_trips'].sum() / total_trips * 100:.1f}%</strong> of trips could shift {adjective} to transit, <strong>{df[(df[f'{st.session_state.phase}_walk_shift']) & (df['mode'] == Mode.CAR)]['vehicle_trips'].sum() / total_trips * 100:.1f}%</strong> to walk, and <strong>{df[(df[f'{st.session_state.phase}_bike_shift']) & (df['mode'] == Mode.CAR)]['vehicle_trips'].sum() / total_trips * 100:.1f}%</strong> to bike.")
    
    # record of settings for all steps that were run
    bigger_markdown("Below are the steps that were run and their settings (1 for categoricals indicates that it was run).")
    settings = {}
    # iterate over saved step class objects
    for name, step_class in step_class_dict.items():
        # last run
        prev = step_class.get_previous_run()
        # don't show if it was disabled/never run
        if prev == None:
            continue
        # logic to format things correctly
        if step_class.is_continuous():
            if prev[1] == CutoffMode.PCT:
                settings[name] = f"{prev[0] * 100:.0f}th pct"
            elif prev[1] == CutoffMode.RAW:
                settings[name] = f"{prev[0]:.1f} {step_class.get_units()}"
            else:
                raise RuntimeError("Something went wrong with the cutoff mode enum")
        else:
            settings[name] = "1 (categorical)"
    st.write(settings)
    
    # details about walking shifts
    st.header("Shifts to walking")
    
    # get % trips and vmt for each walk step and for overall shifts to walking
    bigger_markdown(r"Below, a table detailing processed steps and the % of car trips and VMT that meet those constraints can be seen.")
    st.table(get_summary_df(df, step_class_dict.values(), Mode.WALK, f"{st.session_state.phase}_walk_shift", st.session_state.phase))
        
    # stacked histogram of duration difference for feasible drive, non-feasible drive, and walk trips
    bigger_markdown("Below, a stacked histogram detailing the travel time difference distributions for drive trips that can feasibly shift to walk, drive trips that can't shift, and observed walk trips can be seen.")
    
    st.plotly_chart(stacked_shift_histogram(df, Mode.WALK, "walk_duration_rerouted", f"{st.session_state.phase}_walk_shift", st.session_state.phase), use_container_width=True)
    
    # get df of the % of trips/vmt that are within x minutes of walking
    bigger_markdown(f"The % of car trips and VMT that are {st.session_state.phase} and within x minutes from walking can be seen in the below table.")
    st.table(get_duration_diff_df(df, Mode.WALK, f"{st.session_state.phase}_walk_shift", "walk_duration_rerouted"))
    
    # details about biking shifts
    st.header("Shifts to biking")
    
    # get % trips and vmt for each walk step and for overall shifts to biking
    bigger_markdown(r"Below, a table detailing processed steps and the % of car trips and VMT that meet those constraints can be seen.")
    st.table(get_summary_df(df, step_class_dict.values(), Mode.BIKE, f"{st.session_state.phase}_bike_shift", st.session_state.phase))
        
    # stacked histogram of duration difference for feasible drive, non-feasible drive, and bike trips
    bigger_markdown("Below, a stacked histogram detailing the travel time difference distributions for drive trips that can feasibly shift to biking, drive trips that can't shift, and observed biking trips can be seen.")
    
    st.plotly_chart(stacked_shift_histogram(df, Mode.BIKE, "bike_duration_rerouted", f"{st.session_state.phase}_bike_shift", st.session_state.phase), use_container_width=True)
    
    # get df of the % of trips/vmt that are within x minutes of biking
    bigger_markdown(f"The % of car trips and VMT that are {st.session_state.phase} and within x minutes from walking can be seen in the below table.")
    st.table(get_duration_diff_df(df, Mode.BIKE, f"{st.session_state.phase}_bike_shift", "bike_duration_rerouted"))
    
    # details about biking shifts
    st.header("Shifts to transit")
    
    # get % trips and vmt for each transit step and for overall shifts to transit
    bigger_markdown(r"Below, a table detailing processed steps and the % of car trips and VMT that meet those constraints can be seen.")
    st.table(get_summary_df(df, step_class_dict.values(), Mode.TRANSIT, f"{st.session_state.phase}_transit_shift", st.session_state.phase))
        
    # stacked histogram of duration difference for feasible drive, non-feasible drive, and transit trips
    bigger_markdown("Below, a stacked histogram detailing the travel time difference distributions for drive trips that can feasibly shift to transit, drive trips that can't shift, and observed transit trips can be seen. NOTE: due to the need to filter out trips with no valid transit trip (and thus no applicable transit duration), there are no infeasible drive trips within this histogram.")
    
    st.plotly_chart(stacked_shift_histogram(df[(~df["transit_rerouting_missing"])&(df["transit_duration_rerouted"]>0)&(df["transit_duration_rerouted"]<1440)], Mode.TRANSIT, "transit_duration_rerouted", f"{st.session_state.phase}_transit_shift", st.session_state.phase), use_container_width=True)
    
    # get df of the % of trips/vmt that are within x minutes of transit
    bigger_markdown(f"The % of car trips and VMT that are {st.session_state.phase} and within x minutes from transit can be seen in the below table.")
    st.table(get_duration_diff_df(df[~df["transit_rerouting_missing"]], Mode.TRANSIT, f"{st.session_state.phase}_transit_shift", "transit_duration_rerouted"))
    
    st.header("Shifts to any mode")
    
    # overall % of trips/vmt that can shift given the run constraints
    # NOTE: the overall %s will be 100% if some mode had no applicable steps run (since there was no restriction on shifting to that)
    bigger_markdown(r"Below, the % of car trips/VMT that can shift to the 3 modes/any non-car mode can be seen in table form.")
    overall_shifts = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    overall_shifts["Feasible to switch to walk"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_walk_shift"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_walk_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100: .1f}%'
    ]
    overall_shifts["Feasible to switch to bike"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_bike_shift"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_bike_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%'
    ]
    overall_shifts["Feasible to switch to transit"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_transit_shift"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_transit_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%'
    ]
    overall_shifts["Feasible to switch to any non-car mode"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%'
    ]
    st.table(overall_shifts)
    
    # fastest alternative by mode comparisons
    bigger_markdown(r"Below, the distribution of the duration difference between the best non-car mode and car for shifted trips is shown. Note: a trip can only have a fastest mode if there is a mode that is feasible/likely for it take.")
    df["transit_duration_rerouted_na"] = np.where(df["transit_rerouting_missing"], 9999999, df["transit_duration_rerouted"]) # if no transit trip found, make it very slow to allow other modes to beat it

    # mode must be feasible to be the minimum alternative mode duration
    df["feasible_walk_duration_min"] = np.where(df[f"{st.session_state.phase}_walk_shift"], df["walk_duration_rerouted"], 9999999)
    df["feasible_bike_duration_min"] = np.where(df[f"{st.session_state.phase}_bike_shift"], df["bike_duration_rerouted"], 9999999)
    df["feasible_transit_duration_min"] = np.where(df[f"{st.session_state.phase}_transit_shift"], df["transit_duration_rerouted_na"], 9999999)        
    
    df["min_feasible_alt_mode_duration"] = df[["transit_duration_rerouted_na", "feasible_bike_duration_min", "feasible_walk_duration_min"]].min(axis=1)

    df["fastest_mode"] = "na"
    df["fastest_mode"] = np.where(
        (df[f"{st.session_state.phase}_walk_shift"]) 
        & (df["walk_duration_rerouted"] == df["min_feasible_alt_mode_duration"]),  # is fastest if it is the previously calculated minimum
        Mode.WALK, 
        df["fastest_mode"]
    )
    df["fastest_mode"] = np.where(
        (df[f"{st.session_state.phase}_bike_shift"]) 
        & (df["bike_duration_rerouted"] == df["min_feasible_alt_mode_duration"]),  # is fastest if it is the previously calculated minimum
        Mode.BIKE, 
        df["fastest_mode"]
    )
    df["fastest_mode"] = np.where(
        (df[f"{st.session_state.phase}_transit_shift"]) 
        & (df["transit_duration_rerouted_na"] == df["min_feasible_alt_mode_duration"]),  # is fastest if it is the previously calculated minimum
        Mode.TRANSIT, 
        df["fastest_mode"]
    ) 
       
    # for histograms, calculate difference evenw hen not feasible
    df["min_alt_mode_duration"] = df[["transit_duration_rerouted_na", "bike_duration_rerouted", "walk_duration_rerouted"]].min(axis=1)
    df["min_alt_mode_duration"] = np.where(df["fastest_mode"]=="na", df["min_alt_mode_duration"], df["min_feasible_alt_mode_duration"])
    
    # create a table of the % of car trips/vmt that shifts to each/any mode can mitigate
    overall_shift_comparison = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    overall_shift_comparison["Walk is the fastest alternative"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.WALK)]["vehicle_trips"].sum() / df[df["mode"] == Mode.CAR]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.WALK)]["vmt"].sum() / df[df["mode"] == Mode.CAR]["vmt"].sum() * 100:.1f}%'
    ]
    overall_shift_comparison["Bike is the fastest alternative"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.BIKE)]["vehicle_trips"].sum() / df[df["mode"] == Mode.CAR]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.BIKE)]["vmt"].sum() / df[df["mode"] == Mode.CAR]["vmt"].sum() * 100:.1f}%'
    ]
    overall_shift_comparison["Transit is the fastest alternative"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.TRANSIT)]["vehicle_trips"].sum() / df[df["mode"] == Mode.CAR]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.TRANSIT)]["vmt"].sum() / df[df["mode"] == Mode.CAR]["vmt"].sum() * 100:.1f}%'
    ]
    overall_shift_comparison["Feasible to switch to any non-car mode"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%'
    ]
    st.table(overall_shift_comparison)
    
    # histogram for min travel time difference for all modes
    bigger_markdown(r"Below, the distribution of the duration difference between the best non-car mode and car for shifted trips is shown")
    fig1 = total_shift_histogram(df, st.session_state.phase)
    df["min_alt_mode_minus_car_duration"] = (df["min_feasible_alt_mode_duration"] - df["car_duration_rerouted"])
    st.plotly_chart(fig1, use_container_width=True)
    
    # table for fastest alternative mode being within x minutes of driving
    bigger_markdown(f"The % of car trips and VMT that are {st.session_state.phase} and within x minutes from the fastest alternative mode can be seen in the below table.")
    df["min_alt_mode_minus_car_duration"] = (df["min_feasible_alt_mode_duration"] - df["car_duration_seconds_adj"]) / 60
    duration_diff_df = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    duration_diff_df["Fastest mode is within 5 minutes of driving"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"]) & (df["min_alt_mode_minus_car_duration"] <= 5)]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"]) & (df["min_alt_mode_minus_car_duration"] <= 5)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%'
    ]
    duration_diff_df["Fastest mode is within 15 minutes of driving"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"]) & (df["min_alt_mode_minus_car_duration"] <= 15)]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"]) & (df["min_alt_mode_minus_car_duration"] <= 15)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%'
    ]
    duration_diff_df["Fastest mode is within 30 minutes of driving"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"]) & (df["min_alt_mode_minus_car_duration"] <= 30)]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"]) & (df["min_alt_mode_minus_car_duration"] <= 30)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%'
    ]
    st.table(duration_diff_df)
    
    # various maps showing how metrics are distributed across geographies
    st.header("Geography")
    
    # map of the % of trips in each community regino that can shift given the restrictions
    
    # get a dummy communities df with a column for the proportion of people that could shift in an area    
    community_pct = df.groupby(["CTU",f"{st.session_state.phase}_shift"])[["vehicle_trips"]].sum().reset_index()
    community_pct['percent_vehicle_trips'] = round(100* community_pct['vehicle_trips'] / community_pct.groupby("CTU")['vehicle_trips'].transform('sum'),1)
    community_pct.set_index("CTU", inplace=True)
    values = community_pct[community_pct[f"{st.session_state.phase}_shift"]==1]['percent_vehicle_trips'].fillna(0)
    communities = get_communities()
    communities[f"Percent of vehicle trips that can shift {adjective}"] = values
    
    # create a choropleth mapbox using this (use mapbox since this allows for the desired projection)
    bigger_markdown(f"This map shows the percent of vehicle trips in each community region that can {adjective} shift to any alternative non-car mode.")
    fig2 = px.choropleth_mapbox(communities, 
                         geojson=communities.geometry, 
                         locations=communities.index, 
                         color=f"Percent of vehicle trips that can shift {adjective}", 
                         range_color=(0, 100), 
                         color_continuous_scale="viridis_r",
                         mapbox_style="carto-positron",
                         center={"lat": 44.9778, "lon": -93.2650},
                         opacity=0.8,
    )
    fig2.update_layout(margin=dict(l=0, r=0, b=0, t=40),
                width=900, 
                height=500,
                title=dict(
                    text=f"Percent of vehicle trips in that can shift {adjective} to any non-car mode",
                    x=0.4,
                    y=0.98,
                    xanchor="center",
                    font=dict(size=18)
                )
    )
    fig2.update_geos(fitbounds="locations", visible=False)
    st.plotly_chart(fig2, use_container_width=True)
    
    # map of % of trips in each community regino that can shift competitively when considering the fastest alternative mode
    
    # use previously used dummy communities df to store this metric for each geography
    df["competitive_timing"] = df["min_alt_mode_minus_car_duration"] <= 15
    
    community_pct = df.groupby(["CTU","competitive_timing"])[["vehicle_trips"]].sum().reset_index()
    community_pct['percent_vehicle_trips'] = round(100* community_pct['vehicle_trips'] / community_pct.groupby("CTU")['vehicle_trips'].transform('sum'),1)
    community_pct.set_index("CTU", inplace=True)
    values_competitive = community_pct[community_pct["competitive_timing"]==1]['percent_vehicle_trips'].fillna(0)
    communities[f"Percent of vehicle trips that can shift {adjective}"] = values_competitive
    
    # create the choropleth mapbox
    bigger_markdown(f"This map shows the percent of vehicle trips in each community region that can competitively shift (maximum bidirectional difference of 15 minutes) to the fastest alternative non-car mode.")
    fig3 = px.choropleth_mapbox(communities, 
                         geojson=communities.geometry, 
                         locations=communities.index, 
                         color=f"Percent of vehicle trips that can shift {adjective}",
                         color_continuous_scale="viridis_r", 
                         range_color=(0, 100),
                         mapbox_style="carto-positron",
                         center={"lat": 44.9778, "lon": -93.2650},
                         opacity=0.8
    )
    fig3.update_layout(margin=dict(l=0, r=0, b=0, t=40),
                title=dict(
                    text="Proportion of vehicle trips in CTUs that can competitively shift to a non-car mode",
                    font=dict(size=18),
                    x=0.4,
                    y=0.98,
                    xanchor="center"
                ),
                width=900, 
                height=500
    )
    fig3.update_geos(fitbounds="locations", visible=False)
    st.plotly_chart(fig3, use_container_width=True)
    
    # display various raw metrics regarding shifts/other indicators
    st.header("Raw metrics")
    
    # person trip count before/after mode shifts
    bigger_markdown(inspect.cleandoc(
        f"""- Total number of person trips on car before applying mode shifts: <strong>{round(df[df['mode'] == Mode.CAR]["person_trips"].sum()):,}</strong>
            - Total number of person trips on car after applying mode shifts: <strong>{round(df[(df['mode'] == Mode.CAR) & (~df[f'{st.session_state.phase}_shift'])]["person_trips"].sum()):,}</strong>"""
        )
    )
    
    st.text("")
    
    # vehicle trp count before/after mode shifts
    bigger_markdown(inspect.cleandoc(
        f"""- Total number of vehicle trips on car before applying mode shifts: <strong>{round(df[df['mode'] == Mode.CAR]['vehicle_trips'].sum()):,}</strong>
            - Total number of vehicle trips on car after applying mode shifts: <strong>{round(df[(df['mode'] == Mode.CAR) & (~df[f'{st.session_state.phase}_shift'])]['vehicle_trips'].sum()):,}</strong>"""
        )
    )
    
    st.text("")
    
    # VMT before/after mode shifts
    bigger_markdown(inspect.cleandoc(
        f"""- Total VMT before applying {st.session_state.phase} mode shift: <strong>{round(df[df['mode'] == Mode.CAR]['vmt'].sum()):,}</strong>
        - Total VMT after applying {st.session_state.phase} mode shift: <strong>{round(df[(df['mode'] == Mode.CAR) & (~df[f'{st.session_state.phase}_shift'])]['vmt'].sum()):,}</strong>"""
        )
    )
    
    st.text("")
    
    # run cold start logic (this takes a bit, hence the spinner) to see cold starts before/after shifts
    with st.spinner("Running cold start logic"):
        cold_starts_df = get_cold_starts_df(df[df["mode"] == Mode.CAR])
        print(cold_starts_df)
        
        before_cold_starts = cold_starts_df["num_cold_starts"].sum()
        after_cold_starts = cold_starts_df[cold_starts_df["person_id"].isin(df[(df['mode'] == Mode.CAR) & (~df[f'{st.session_state.phase}_shift'])]["person_id"])]["num_cold_starts"].sum()

        if (~df[f"{st.session_state.phase}_shift"]).sum() == 0:
            after_cold_starts = 0
        
    # cold shifts before/after mode shifts
    bigger_markdown(inspect.cleandoc(
        f"""- Number of cold starts before applying {st.session_state.phase} mode shifts: <strong>{before_cold_starts:,}</strong>
            - Number of cold starts after applying {st.session_state.phase} mode shifts: <strong>{after_cold_starts:,}</strong>"""
        )
    )
    
    # various bar charts showing the ability to shift across various categories
    st.header("Shifts by categories")
    
    # ability to shift when segmented by income bracket
    bigger_markdown(r"Below, the % of vehicle trips that can shift when segmented by income bracket is shown.")
    
    # get the % of vehicle trips in each income group that can shift & reorder the columns into a readable order
    income_pct = df.groupby(["income_cleaned",f"{st.session_state.phase}_shift"])[["vehicle_trips"]].sum().reset_index()
    income_pct['percent_vehicle_trips'] = round(100* income_pct['vehicle_trips'] / income_pct.groupby('income_cleaned')['vehicle_trips'].transform('sum'),1)
    
    # creat the barplot
    fig4 = px.bar(income_pct[income_pct[f"{st.session_state.phase}_shift"]], 
                  x='income_cleaned', 
                  y='percent_vehicle_trips', 
                  color='vehicle_trips', 
                  range_color=(0, 2000000), 
                  labels={'percent_vehicle_trips':'Percent of vehicle trips', 
                          'vehicle_trips': 'Total vehicle trips'},
                  category_orders = dict(income_cleaned=["Under $25,000", "$25,000-$49,999","$50,000-$74,999","$75,000-$99,999","$100,000-$149,999", "$150,000 or more","na"]))
    fig4.update_layout(
        title={
            'text': 'Percent of vehicle trips that can shift modes by income group',
            'font': dict(
                size=18
            ),
            'x': 0.5, 
            'xanchor': 'center',
            'y': 0.9
        },
        xaxis_title=dict(text="Income group", font=dict(size=16)),
        yaxis_title=dict(text=f"Percent of vehicle trips in the<br>category that can {adjective} shift", font=dict(size=16)),
        showlegend=False
    )
    st.plotly_chart(fig4, use_container_width=True)
    
    # ability to shift by trip purpose (usually destination purpose unless destination is home, then origin purpose -- this is done in the intiialization step)
    bigger_markdown(r"Below, the % of vehicle trips that can shift when segmented by trip purpose are shown.")
    
    purpose_pct = df.groupby(["purpose_cleaned",f"{st.session_state.phase}_shift"])[["vehicle_trips"]].sum().reset_index()
    purpose_pct['percent_vehicle_trips'] = round(100* purpose_pct['vehicle_trips'] / purpose_pct.groupby('purpose_cleaned')['vehicle_trips'].transform('sum'),1)
    
    fig5 = px.bar(purpose_pct[purpose_pct[f"{st.session_state.phase}_shift"]], 
                  x='purpose_cleaned', 
                  y='percent_vehicle_trips', 
                  color='vehicle_trips', 
                  range_color=(0, 2000000), 
                  labels={'percent_vehicle_trips':'Percent of vehicle trips', 
                          'vehicle_trips': 'Total vehicle trips'},
                  category_orders = dict(purpose_cleaned=["Work", "School", "Escort", "Shop", "Errand", "Meal", "Social/Recreation", "Other"]))
    fig5.update_layout(
        title={
            'text': 'Percent of vehicle trips that can shift mode by trip purpose',
            'font': dict(
                size=18
            ),
            'x': 0.5, 
            'xanchor': 'center',
            'y': 0.9
        },
        xaxis_title=dict(text="Trip Purpose", font=dict(size=16)),
        yaxis_title=dict(text=f"Percent of vehicle trips in the<br>category that can {adjective} shift", font=dict(size=16)),
        legend=dict(font=dict(size=16)),
        showlegend=False
    )
    st.plotly_chart(fig5, use_container_width=True)
    
    # ability to shift by person type (adult, student, etc.)
    bigger_markdown(r"Below, the % of vehicle trips that can shift when segmented by person type are shown.")
                
    person_pct = df.groupby(["person_type",f"{st.session_state.phase}_shift"])[["vehicle_trips"]].sum().reset_index()
    person_pct['percent_vehicle_trips'] = round(100* person_pct['vehicle_trips'] / person_pct.groupby('person_type')['vehicle_trips'].transform('sum'),1)
    
    fig6 = px.bar(person_pct[person_pct[f"{st.session_state.phase}_shift"]], 
                  x='person_type', 
                  y='percent_vehicle_trips', 
                  color='vehicle_trips', 
                  range_color=(0, 3000000), 
                  labels={'percent_vehicle_trips':'Percent of vehicle trips', 
                          'vehicle_trips': 'Total vehicle trips'},
                  category_orders = dict(person_type=["Working adult with kids", "Working adult without kids", "Non-working adult with kids","Non-working adult without kids","Retired","College student","Child"]))
    fig6.update_layout(
        title={
            'text': 'Percent of vehicle trips that can shift mode by person type',
            'font': dict(
                size=18
            ),
            'x': 0.5, 
            'xanchor': 'center',
            'y': 0.9
        },
        xaxis_title=dict(text="Person type", font=dict(size=16)),
        yaxis_title=dict(text=f"Percent of vehicle trips in the<br>category that can {adjective} shift", font=dict(size=16)),
        legend=dict(font=dict(size=16)),
        showlegend=False
    )
    st.plotly_chart(fig6, use_container_width=True)
    
    # ability to shift by gender
    bigger_markdown(r"Below, the % of trips that can shift when segmented by gender are shown.")
                
    gender_pct = df.groupby(["gender_cleaned",f"{st.session_state.phase}_shift"])[["vehicle_trips"]].sum().reset_index()
    gender_pct['percent_vehicle_trips'] = round(100* gender_pct['vehicle_trips'] / gender_pct.groupby('gender_cleaned')['vehicle_trips'].transform('sum'),1)
    
    fig7 = px.bar(gender_pct[gender_pct[f"{st.session_state.phase}_shift"]], 
                  x='gender_cleaned', 
                  y='percent_vehicle_trips', 
                  color='vehicle_trips', 
                  range_color=(0, 5000000), 
                  labels={'percent_vehicle_trips':'Percent of vehicle trips', 
                          'vehicle_trips': 'Total vehicle trips'})
    fig7.update_layout(
        title={
            'text': 'Percent of vehicle trips that can shift mode by gender',
            'font': dict(
                size=18
            ),
            'x': 0.5, 
            'xanchor': 'center',
            'y': 0.9
        },
        xaxis_title=dict(text="Gender", font=dict(size=16)),
        yaxis_title=dict(text=f"Percent of vehicle trips in the<br>category that can {adjective} shift", font=dict(size=16)),
        legend=dict(font=dict(size=16)),
        showlegend=False
    )
    st.plotly_chart(fig7, use_container_width=True)
    
    # ability to shift by recorded TBI wave (either 1/2)
    bigger_markdown(r"Below, the % of trips that can shift when segmented by TBI wave is shown.")
                
    wave_pct = df.groupby(["wave",f"{st.session_state.phase}_shift"])[["vehicle_trips"]].sum().reset_index()
    wave_pct['percent_vehicle_trips'] = round(100* wave_pct['vehicle_trips'] / wave_pct.groupby('wave')['vehicle_trips'].transform('sum'),1)
    
    fig8 = px.bar(wave_pct[wave_pct[f"{st.session_state.phase}_shift"]], 
                  x='wave', 
                  y='percent_vehicle_trips', 
                  color='vehicle_trips',
                  range_color=(0, 5000000), 
                  labels={'percent_vehicle_trips':'Percent of vehicle trips', 
                          'vehicle_trips': 'Total vehicle trips'})
    fig8.update_layout(
        title={
            'text': 'Percent of vehicle trips that can shift mode by TBI wave',
            'font': dict(
                size=18
            ),
            'x': 0.5, 
            'xanchor': 'center',
            'y': 0.9
        },
        xaxis_title=dict(text="Wave", font=dict(size=16)),
        yaxis_title=dict(text=f"Percent of vehicle trips in the<br>category that can {adjective} shift", font=dict(size=16)),
        legend=dict(font=dict(size=16)),
        showlegend=False
    )
    st.plotly_chart(fig8, use_container_width=True)
    
    # various metrics for tour-level shifts that are possible
    st.header("Tour-level shifts")
    
    # a tour can shift to a mode if and only if all component trips can shift to that mode
    temp = pd.merge(
        left=df[["wave", "person_id", "travel_date"]],
        right=df.groupby(["wave", "person_id", "travel_date"]).agg({
            f"{st.session_state.phase}_walk_shift": "all",
            f"{st.session_state.phase}_bike_shift": "all",
            f"{st.session_state.phase}_transit_shift": "all"
        }),
        left_on=["wave", "person_id", "travel_date"],
        right_index=True,
        how="left"
    )
    # a little fanagling to change df in-place
    df[f"{st.session_state.phase}_walk_shift_tour"] = temp[f"{st.session_state.phase}_walk_shift"]
    df[f"{st.session_state.phase}_bike_shift_tour"] = temp[f"{st.session_state.phase}_bike_shift"]
    df[f"{st.session_state.phase}_transit_shift_tour"] = temp[f"{st.session_state.phase}_transit_shift"]
    
    # a tour can shift if it can shift to any individual mode
    df[f"{st.session_state.phase}_shift_tour"] = (
        df[f"{st.session_state.phase}_walk_shift_tour"] | df[f"{st.session_state.phase}_bike_shift_tour"] | df[f"{st.session_state.phase}_transit_shift_tour"]
    )
    
    # create a dataframe to show the % of car trips/vmt that can be mitigated when considering only tour-level shifts as possible and display this in streamlit
    tour_df = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    tour_df["Feasible to switch to walk"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_walk_shift_tour"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_walk_shift_tour"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    tour_df["Feasible to switch to bike"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_bike_shift_tour"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_bike_shift_tour"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    tour_df["Feasible to switch to transit"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_transit_shift_tour"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_transit_shift_tour"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    tour_df["Feasible to switch to any non-car mode"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift_tour"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift_tour"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    
    bigger_markdown(f"We consider a tour-level shift possible if every component trip can also shift {adjective}.")
    st.table(tour_df)
    
def final_summary() -> None:
    
    # define the actions we can do at this point
    st.sidebar.header("Actions")
    
    # button to allow shift to feasible step; only possible if currently in feasible and probable not disabled
    if st.session_state.phase == Phase.FEASIBLE:
        if st.sidebar.button("Move to probable step"):
            logging.info("Moving to probable step")
            st.session_state.summary_screen = False
            st.session_state.start_screen_probable = True
            st.experimental_rerun()
    
    # rerun current phase from step selection 
    if st.sidebar.button("Rerun visualization tool phase"):
        logging.info(f"Rerunning current ({st.session_state.phase}) phase of the tool")
        
        # turn off the summary screen and turn on the desired start screen and refresh
        st.session_state.summary_screen = False
        if st.session_state.phase == Phase.FEASIBLE:
            st.session_state.start_screen_feasible = True
        elif st.session_state.phase == Phase.PROBABLE:
            st.session_state.start_screen_probable = True
        st.experimental_rerun()
        
    # currently not supported to go back all the way--can just refresh to do so
    if st.sidebar.button("Start visualization tool from beginning", disabled=True):
        pass
                
    if st.session_state.have_scenarios:
        col1, col2 = st.columns(2, gap="medium")
        with col1:
            show_final_summary(st.session_state.df, st.session_state.step_class_dict)
        with col2:
            show_final_summary(st.session_state.sdf, st.session_state.step_class_scenario_dict)
            
    else:
        show_final_summary(st.session_state.df, st.session_state.step_class_dict)
        
    if not handler["build"]:
        if st.sidebar.button(f"Save current result to csv"):
            with st.spinner("Exporting dataframe and percentiles"):
                st.session_state.df.to_csv(f"output/{st.session_state.phase}_trips.csv", index=False)
                if st.session_state.have_scenarios:
                    st.session_state.sdf.to_csv(f"output/{st.session_state.phase}_trips_scenario.csv", index=False)
    
def show_step() -> None:
    """
    This function generates the step we are currently at, including all information blurbs/interactiveness. 
    """
    
    # get an alias to the current step for easy reference later
    curr: steps.BaseStep = st.session_state.step_class_dict[st.session_state.step]
    # title the page by the step name
    st.title(curr.get_name())
        
    # if we have scenarios, get the scenario class from the scenario dict
    if st.session_state.have_scenarios:
        scenario_class: steps.BaseStep = st.session_state.step_class_scenario_dict[st.session_state.step]
        
    # determine whether we are actually in a scenario (and need to split into columns)
    cur_scenario = in_scenario(curr.get_mode(), st.session_state.phase, st.session_state.step, st.session_state.scenarios)
        
    if curr.is_continuous():
        curr.set_cutoff_mode(st.sidebar.radio("Choose how to set the cutoff", (CutoffMode.PCT, CutoffMode.RAW), key=st.session_state.id))
            
        # synchronize the cutoff modes
        if st.session_state.have_scenarios:
            scenario_class.set_cutoff_mode(curr.get_cutoff_mode())
            
        # percentile cutoff mode handler
        if curr.get_cutoff_mode() == CutoffMode.PCT:
            # handle base scenario things
            curr.set_cutoff(st.sidebar.slider("Select a value:", 0.0, 1.0, 0.95, 0.01, key=st.session_state.id + 1))
            st.sidebar.markdown(f"Cutoff equivalent: {curr.get_cutoff_equivalent():.1f} {curr.get_units()}")
            
            # if in scenario, allow the cutoff to be set separately
            if cur_scenario:
                scenario_class.set_cutoff(st.sidebar.slider("Select a scenario value:", 0.0, 1.0, 0.95, 0.01, key=st.session_state.id + 3))
                st.sidebar.markdown(f"Scenario cutoff equivalent: {scenario_class.get_cutoff_equivalent():.1f} {scenario_class.get_units()}")
            # synchronize the cutoffs if possible
            elif st.session_state.have_scenarios:
                scenario_class.set_cutoff(curr.get_cutoff())
        # repeat the previous logic but with raw cutoffs now -- only difference is in ranges of allowed cutoffs
        elif curr.get_cutoff_mode() == CutoffMode.RAW:
            extrema = curr.get_extrema()
            
            curr.set_cutoff(st.sidebar.slider("Select a value:", float(extrema[0]), float(extrema[1]), float(extrema[1]), float((extrema[1] - extrema[0]) / 100), format=f"%0.1f {curr.get_units()}", key=st.session_state.id + 2))
            st.sidebar.markdown(f"Cutoff equivalent: {curr.get_cutoff_equivalent():.1f} percentile")
            
            # if in scenario, allow the cutoff to be set separately
            if cur_scenario:
                scenario_extrema = scenario_class.get_extrema()
                scenario_class.set_cutoff(st.sidebar.slider("Select a scenario value:", float(scenario_extrema[0]), float(scenario_extrema[1]), float(scenario_extrema[1]), float((scenario_extrema[1] - scenario_extrema[0]) / 100), format=f"%0.1f {scenario_class.get_units()}", key=st.session_state.id + 4))
                st.sidebar.markdown(f"Scenario cutoff equivalent: {scenario_class.get_cutoff_equivalent():.1f} percentile")
            # synchronize the raw cutoffs if there is a scenario to do so
            elif st.session_state.have_scenarios:
                scenario_class.set_cutoff(curr.get_cutoff())
            
        else:
            logging.exception(f"Something went worng with the cutoff mode enum: {curr.get_cutoff_mode()}")
            raise RuntimeError("something went wrong")
    
    # button to dsiable the current step
    if st.sidebar.button("Disable step", use_container_width=True):
        curr.disable()
        
        # synchronize the disables
        if st.session_state.have_scenarios:
            scenario_class.disable()
        
        
    # button to apply (& show the entire narrative of the current step); otherwise, just have a blurb on the current step/how to run it
    if st.sidebar.button("Apply step", use_container_width=True):
        curr.apply_step()
        
        # apply step if there is a scenario object
        if st.session_state.have_scenarios:
            scenario_class.apply_step()

        if not st.session_state.fast_mode:
            # if we are currently in a scenario, split into columns to display both
            if cur_scenario:
                col1, col2 = st.columns(2, gap="medium")
                with col1:
                    curr.show_step_streamlit()
                with col2:
                    scenario_class.show_step_streamlit()
            # otherwise just show the base one (covers both of them even if have_scenarios is True)
            else:
                curr.show_step_streamlit()
        else:
            bigger_markdown("Step applied")
        
    else:
        st.header("Click the apply step button once the desired settings have been set or click disable to disable the step.")
        bigger_markdown(curr.get_desc())

def run() -> None:
    """
    This function provides the main wrapper for the visualization tool, implementing actions like switching between steps/moving to sumary
    """
    
    # define possible actions
    st.sidebar.header("Actions")
    option_slot = st.sidebar.empty()

    # finish and move to summary button -- toggle summary screen to true & refresh
    if st.sidebar.button("Finish and move to summary"):
        logging.info("Moving to the summary step")
        st.session_state.summary_screen = True
        st.experimental_rerun()
    
    # have the ability to choose what step to run (with segmentation based on phase)
    # can only go to new steps; TODO: add functionality to save snapshots after each step is left to allow full backtracking
    if st.session_state.phase == Phase.FEASIBLE:
        steps = [step for step in st.session_state["feasible_steps"] if step not in st.session_state.step_class_dict or step == st.session_state.step or (step in st.session_state.step_class_dict and st.session_state.step_class_dict[step].get_previous_run() == None)]
        option = option_slot.selectbox(
            "Choose the step you want to run. If you move away from the current step, the settings of the current step will be 'locked in' and will be unable to be changed.",
            steps,
            index=steps.index(st.session_state.step)
        )
    elif st.session_state.phase == Phase.PROBABLE:
        steps = [step for step in st.session_state["feasible_steps"] if step not in st.session_state.step_class_dict or step == st.session_state.step or (step in st.session_state.step_class_dict and st.session_state.step_class_dict[step].get_previous_run() == None)]
        option = option_slot.selectbox(
            "Choose the step you want to run. If you move away from the current step, the settings of the current step will be 'locked in' and will be unable to be changed.",
            steps,
            index=steps.index(st.session_state.step)
        )
    else:
        logging.exception(f"something went wrong with the overall step session state variable: {st.session_state.phase}")
        raise RuntimeError("Something went wrong with the overall step session state variable")
    
    # manual refresh of the tool -- may break the tool
    if st.sidebar.button("Refresh"):
        logging.info("Refreshing the tool")
        st.experimental_rerun()
        
    # logic if we swithced steps (selected step is not equal to the stored step)
    if option is not None and st.session_state.step != option:
        logging.info(f"Moving to new step {option} from step {st.session_state.step}")
        
        # update current step
        st.session_state.step = option
        
        # if the step has already been created, retrieve it from the dictionary
        if False and option in st.session_state.step_class_dict:  # currently disabled -- backtracking breaks things without some kind of "commit" structure
            logging.info("Retrieving existing instantiation of the new step")
            st.session_state.step_class = st.session_state.step_class_dict[option]
        # otherwise, create it from scratch
        else:
            logging.info("Creating the new step for the first time")

            # if we have scenarios, we need to create a class object for both the base/scenario pipelines
            if st.session_state.have_scenarios:
                st.session_state.step_class_dict[option] = create_base_step(option)
                st.session_state.step_class_scenario_dict[option] = create_scenario_step(option)
            # otherwise just create the base one
            else:
                st.session_state.step_class_dict[option] = create_base_step(option)
            st.session_state.id += 10
            # st.experimental_rerun()
            
    # show the meat of the current step
    show_step()
    
    # create a dropdown showing the steps that have already been run & their associated cutoffs
    d = defaultdict(lambda: dict())
    
    show_previous_runs(st.session_state.step_class_dict, "base", d)
    
    if st.session_state.have_scenarios:
        show_previous_runs(st.session_state.step_class_scenario_dict, "scenario", d)
    
    with st.sidebar.expander("See previously run steps"):
        st.write(d)
    
    # blurb about exporting to PDF from webpage
    st.sidebar.markdown("To export this page to PDF, click the x button above to dismiss the sidebar, and then manually print to PDF")
    
# main serving function of strealit application
if __name__ == "__main__":
    st.set_page_config(layout="wide")
    # hacky function to allow for bigger font sizes
    st.markdown(
        """
            <style>
                .bigger-font {
                    font-size: 1.2rem !important;
                }
            </style>
        """, 
        unsafe_allow_html=True
    )
    
    # do initiali variable setup; this only runs on first startup
    # this forces the tool to start at start screen feasible
    if "start_screen_feasible" not in st.session_state:
        logging.info("Doing initial setup")
        st.session_state["start_screen_feasible"] = True
        st.session_state["start_screen_probable"] = False
        st.session_state.id = 0
    
    # main page handler -- in general, if any session state page indicator is True, run that and only one indicator should be True at a time
    
    # initial setup again -- setup df
    if "df" not in st.session_state:
        with st.spinner("Setting up application"):
            setup_df()
        st.experimental_rerun()
    # run the start screen for the feasible phase
    elif st.session_state.start_screen_feasible:
        start_screen_feasible()
    # run the start screen for the probable phase
    elif st.session_state.start_screen_probable:
        start_screen_probable()
    # run the summary screen
    elif st.session_state.summary_screen:
        final_summary()
    # default -- only runs with no indicators -- shows the current step/wrapper for the tool
    else:
        run()