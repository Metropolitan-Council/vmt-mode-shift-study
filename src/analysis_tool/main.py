import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import inspect
import matplotlib.pyplot as plt
import seaborn as sns
import keyring

import steps
from initialize import prepare_data
from settings import handler, get_communities
from steps.enums import *
from util import get_num_cold_starts, add_value_labels, rvb, stateful_button, stacked_shift_histogram, get_summary_df, get_duration_diff_df
import json

def start_screen():
    st.title("Select the steps that you would like to run")
    
    st.session_state["feasible_steps"] = []
    st.session_state["probable_steps"] = []
    st.session_state["feasible_disabled"] = False
    st.session_state["probable_disabled"] = False
    
    st.sidebar.header("Actions")
    
    # NOTE: disabling the feasible phase is untested and may fail if commented back in--the code was written under the assumption that the feasible phase is always ran first before the probable section
    # if stateful_button("Disable feasible phase", key="feasible_button"):
    #     st.session_state["feasible_disabled"] = True
    if stateful_button("Disable probable phase", key="probable_button"):
        st.session_state["probable_disabled"] = True
        
    if st.sidebar.button("Begin"):
        st.session_state["finish_start"] = True
        st.experimental_rerun()
    if st.sidebar.button("Begin with all steps selected"):
        st.session_state["feasible_steps"] = handler["feasible_steps"]
        st.session_state["probable_steps"] = handler["probable_steps"]
        st.session_state["finish_start"] = True
        st.experimental_rerun()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("Feasible")
        
        for step in handler["feasible_steps"]:
            if st.checkbox(f"Feasible - {step}", disabled=st.session_state["feasible_disabled"]):
                st.session_state["feasible_steps"].append(step)
            else:
                if step in st.session_state["feasible_steps"]:
                    st.session_state["feasible_steps"].remove(step)
                    
    with col2: 
        st.header("Probable")
        
        for step in handler["probable_steps"]:
            if st.checkbox(f"Probable - {step}", disabled=st.session_state["probable_disabled"]):
                st.session_state["probable_steps"].append(step)
            else:
                if step in st.session_state["probable_steps"]:
                    st.session_state["probable_steps"].remove(step)

@st.cache_resource
def setup_inputs():
    drive_data_dir = keyring.get_password('msp', 'vmt_reduction_dir')
        
    if handler["force_reinitialize"]:
        raw = pd.read_csv(drive_data_dir + "/data_processed/tbi_cleaned.csv", usecols=handler["keep_columns"])

        df = prepare_data(raw, drive_data_dir)
    else:
        try:
            df = pd.read_csv("data/" + handler["tbi_file_name"])
            
        except Exception as e:
            raw = pd.read_csv(drive_data_dir + "/data_processed/tbi_cleaned.csv", usecols=handler["keep_columns"])

            df = prepare_data(raw, drive_data_dir)
            
    # everything is feasible initially
    df[f'{Phase.FEASIBLE}_{Mode.WALK}_shift'] = True
    df[f'{Phase.FEASIBLE}_{Mode.BIKE}_shift'] = True
    df[f'{Phase.FEASIBLE}_{Mode.TRANSIT}_shift'] = True
    df[f'{Phase.FEASIBLE}_shift'] = True
    
    try:
        if not st.session_state["feasible_disabled"]:
            st.session_state["step"] = st.session_state["feasible_steps"][0]
            st.session_state["phase"] = Phase.FEASIBLE
            st.session_state["overall_step"] = steps.feasible_steps
        elif not st.session_state["probable_disabled"]:
            st.session_state["step"] = st.session_state["probable_steps"][0]
            st.session_state["phase"] = Phase.PROBABLE
            st.session_state["overall_step"] = steps.probable_steps
        else:
            raise RuntimeError("No steps selected")
    except IndexError as e:
        print("No steps selected")
        raise e
        
    st.session_state["df"] = df
    st.session_state["step_class_dict"] = dict()
    st.session_state["step_class_dict"][st.session_state.step] =  getattr(st.session_state.overall_step, st.session_state.step)(st.session_state.df)
    st.session_state["step_class"] = st.session_state["step_class_dict"][st.session_state.step]
    st.session_state["in_summary"] = False
    # st.session_state["cache"] = dict()
    
    return 0
    
@st.cache_resource
def setup_probable():
    # st.session_state["df_feasible"] = st.session_state.df.copy()
    st.session_state["df"] = st.session_state.df.loc[st.session_state.df["feasible_shift"], :].copy()
    
    df: pd.DataFrame = st.session_state.df
    df[f'{Phase.PROBABLE}_{Mode.WALK}_shift'] = True
    df[f'{Phase.PROBABLE}_{Mode.BIKE}_shift'] = True
    df[f'{Phase.PROBABLE}_{Mode.TRANSIT}_shift'] = True
    df[f'{Phase.PROBABLE}_shift'] = True
    
    st.session_state["phase"] = Phase.PROBABLE
    st.session_state["step"] = "WalkDurationDifferenceStep"
    st.session_state["overall_step"] = steps.probable_steps
    st.session_state["step_class"] = steps.probable_steps.WalkDurationDifferenceStep(df)
    st.session_state["step_class_dict"] = dict()
    st.session_state["in_summary"] = False
    # st.session_state["cache"] = dict()
    
    print("probable setup")
    
    return 0
    
def final_summary():
    # button to allow shift to feasible step; only possible if currently in feasible and probable not disabled
    if st.session_state.phase == Phase.FEASIBLE and not st.session_state["probable_disabled"]:
        if st.sidebar.button("Move to probable step"):
            setup_probable()
            st.experimental_rerun()
    
    # save reference to underlying df for ease of typing
    df: pd.DataFrame = st.session_state.df
    
    # button to save df to csv on disk
    if st.sidebar.button("Save current result to csv"):
        with st.spinner("Exporting dataframe and percentiles"):
            df.to_csv(f"output/{st.session_state.phase}_trips.csv")
            f = open(f"output/{st.session_state.phase}_percentiles.json", "w")
            f.write({step_name: step_class.get_cutoff() for step_name, step_class in st.session_state.step_class_dict.items()})
            f.close()
            
    # calculate overall shift ability -- can shift to at least one mode
    df.loc[:, f"{st.session_state.phase}_shift"] = (
        df[f"{st.session_state.phase}_transit_shift"] | 
        df[f"{st.session_state.phase}_walk_shift"] | 
        df[f"{st.session_state.phase}_bike_shift"]
    )
    
    # save the feasible pct for later use in probable step
    if st.session_state.phase == Phase.FEASIBLE:
        st.session_state["feasible_pct"] = df[df['mode'] == Mode.CAR][f'{st.session_state.phase}_shift'].sum() / len(df[df['mode'] == Mode.CAR])
    
    # summary just has some overall statistics
    st.title("Summary")
    
    # record of settings for all steps that were run
    st.markdown("Below are the steps that were run and their settings (1 for categoricals indicates that it was run).")
    settings = {}
    # iterate over saved step class objects
    for name, step_class in st.session_state.step_class_dict.items():
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
                settings[name] = f"{prev[0]:.2f} units"
            else:
                raise RuntimeError("Something went wrong with the cutoff mode enum")
        else:
            settings[name] = "1 (categorical)"
    st.write(settings)
    
    # details about walking shifts
    st.header("Shifts to walking")
    
    # calculate minutes for future reference
    df["walk_duration_minutes"] = df["walk_duration_seconds"] / 60
    
    # get % trips and vmt for each walk step and for overall shifts to walking
    st.markdown(r"Below, a table detailing processed steps and the % of car trips and VMT that meet those constraints can be seen.")
    st.table(get_summary_df(df, st.session_state.step_class_dict.values(), Mode.WALK, f"{st.session_state.phase}_walk_shift"))
        
    # stacked histogram of duration difference for feasible drive, non-feasible drive, and walk trips
    st.markdown("Below, a stacked histogram detailing the travel time difference distributions for drive trips that can feasibly shift to walk, drive trips that can't shift, and observed walk trips can be seen.")
    
    st.plotly_chart(stacked_shift_histogram(df, Mode.WALK, "walk_duration_minutes", f"{st.session_state.phase}_walk_shift"))
    
    # get df of the % of trips/vmt that are within x minutes of walking
    st.markdown(r"The % of car trips and VMT that are within x minutes from walking can be seen in the below table.")
    st.table(get_duration_diff_df(df, Mode.WALK, "walk_duration_minutes"))
    
    # details about biking shifts
    st.header("Shifts to biking")
    
    # get minutes for future reference
    df["bike_duration_minutes_adj"] = df["bike_duration_seconds_adj"] / 60
    
    # get % trips and vmt for each walk step and for overall shifts to biking
    st.markdown(r"Below, a table detailing processed steps and the % of car trips and VMT that meet those constraints can be seen.")
    st.table(get_summary_df(df, st.session_state.step_class_dict.values(), Mode.BIKE, f"{st.session_state.phase}_bike_shift"))
        
    # stacked histogram of duration difference for feasible drive, non-feasible drive, and bike trips
    st.markdown("Below, a stacked histogram detailing the travel time difference distributions for drive trips that can feasibly shift to biking, drive trips that can't shift, and observed biking trips can be seen.")
    
    print(df[f"{st.session_state.phase}_bike_shift"])
    st.plotly_chart(stacked_shift_histogram(df, Mode.BIKE, "bike_duration_minutes_adj", f"{st.session_state.phase}_bike_shift"))
    
    # get df of the % of trips/vmt that are within x minutes of biking
    st.markdown(r"The % of car trips and VMT that are within x minutes from walking can be seen in the below table.")
    st.table(get_duration_diff_df(df, Mode.BIKE, "bike_duration_minutes_adj"))
    
    # details about biking shifts
    st.header("Shifts to transit")
    
    # get % trips and vmt for each transit step and for overall shifts to transit
    st.markdown(r"Below, a table detailing processed steps and the % of car trips and VMT that meet those constraints can be seen.")
    st.table(get_summary_df(df, st.session_state.step_class_dict.values(), Mode.TRANSIT, f"{st.session_state.phase}_transit_shift"))
        
    # stacked histogram of duration difference for feasible drive, non-feasible drive, and transit trips
    st.markdown("Below, a stacked histogram detailing the travel time difference distributions for drive trips that can feasibly shift to transit, drive trips that can't shift, and observed transit trips can be seen. NOTE: due to the need to filter out trips with no valid transit trip (and thus no appliacble transit duration), there are no infeasible drive trips within this histogram.")
    
    st.plotly_chart(stacked_shift_histogram(df[(~df["transit_duration"].isna())&(df["transit_duration"]>0)&(df["transit_duration"]<1440)], Mode.TRANSIT, "transit_duration", f"{st.session_state.phase}_transit_shift"))
    
    # get df of the % of trips/vmt that are within x minutes of transit
    st.markdown(r"The % of car trips and VMT that are within x minutes from transit can be seen in the below table.")
    st.table(get_duration_diff_df(df[~df["transit_duration"].isna()], Mode.TRANSIT, "transit_duration"))
    
    st.header("Shifts to any mode")
    
    # overall % of trips/vmt that can shift given the run constraints
    # NOTE: the overall %s will be 100% if some mode had no applicable steps run (since there was no restriction on shifting to that)
    st.markdown(r"Below, the % of car trips/VMT that can shift to the 3 modes/any non-car mode can be seen in table form.")
    overall_shifts = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    overall_shifts["Feasible to switch to walk"] = [
        f'{len(df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_walk_shift"])]) / len(df[(df["mode"] == Mode.CAR)]) * 100: .2f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_walk_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100: .2f}%'
    ]
    overall_shifts["Feasible to switch to bike"] = [
        f'{len(df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_bike_shift"])]) / len(df[(df["mode"] == Mode.CAR)]) * 100: .2f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_bike_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.2f}%'
    ]
    overall_shifts["Feasible to switch to transit"] = [
        f'{len(df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_transit_shift"])]) / len(df[(df["mode"] == Mode.CAR)]) * 100:.2f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_transit_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.2f}%'
    ]
    overall_shifts["Feasible to switch to any non-car mode"] = [
        f'{len(df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"])]) / len(df[(df["mode"] == Mode.CAR)]) * 100:.2f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.2f}%'
    ]
    st.table(overall_shifts)
    
    # fastest alternative by mode comparisons
    st.markdown(r"Below, the distribution of the duration difference between the best non-car mode and car for shifted trips is shown")
    df["transit_duration_seconds_na"] = df["transit_duration"].fillna(9999999) * 60 # if no transit trip found, make it very slow to allow other modes to beat it
    df["min_alt_mode_duration"] = df[["transit_duration_seconds_na", "bike_duration_seconds_adj", "walk_duration_seconds"]].min(axis=1)
    df["fastest_mode"] = Mode.WALK
    df["fastest_mode"] = np.where(df["bike_duration_seconds_adj"] == df["min_alt_mode_duration"], Mode.BIKE, df["fastest_mode"]) # is fastest if it is the previously calculated minimum
    df["fastest_mode"] = np.where(df["transit_duration_seconds_na"] == df["min_alt_mode_duration"], Mode.TRANSIT, df["fastest_mode"]) # is fastest if it is the previously calculated minimum
    
    overall_shift_comparison = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    overall_shift_comparison["Walk is the fastest alternative"] = [
        len(df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.WALK)]) / len(df[df["mode"] == Mode.CAR]),
        df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.WALK)]["vmt"].sum() / df[df["mode"] == Mode.CAR]["vmt"].sum()
    ]
    overall_shift_comparison["Bike is the fastest alternative"] = [
        len(df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.BIKE)]) / len(df[df["mode"] == Mode.CAR]),
        df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.BIKE)]["vmt"].sum() / df[df["mode"] == Mode.CAR]["vmt"].sum()
    ]
    overall_shift_comparison["Transit is the fastest alternative"] = [
        len(df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.TRANSIT)]) / len(df[df["mode"] == Mode.CAR]),
        df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.TRANSIT)]["vmt"].sum() / df[df["mode"] == Mode.CAR]["vmt"].sum()
    ]
    overall_shift_comparison["Feasible to switch to any non-car mode"] = [
        len(df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"])]) / len(df[(df["mode"] == Mode.CAR)]),
        df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum()
    ]
    st.table(overall_shift_comparison)
    
    # histogram for min travel time difference for all modes
    # not sure how to do the tradiational stacked histogram with everything in it
    st.markdown(r"Below, the distribution of the duration difference between the best non-car mode and car for shifted trips is shown")
    df["car_minus_min_alt_mode_duration"] = (df["min_alt_mode_duration"] - df["car_duration_seconds_adj"]) / 60
    fig5 = px.histogram(df, x="car_minus_min_alt_mode_duration")
    st.plotly_chart(fig5)
    
    # table for fastest alternative mode being within x minutes of driving
    st.markdown(r"The % of car trips and VMT that are within x minutes from the fastest alternative mode can be seen in the below table.")
    duration_diff_df = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    duration_diff_df["Fastest mode is within 5 minutes of driving"] = [
        f'{len(df[(df["mode"] == Mode.CAR) & (df["car_minus_min_alt_mode_duration"].abs() <= 5)]) / len(df[(df["mode"] == Mode.CAR)]): .2f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df["car_minus_min_alt_mode_duration"].abs() <= 5)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum():.2f}%'
    ]
    duration_diff_df["Fastest mode is within 15 minutes of driving"] = [
        f'{len(df[(df["mode"] == Mode.CAR) & (df["car_minus_min_alt_mode_duration"].abs() <= 15)]) / len(df[(df["mode"] == Mode.CAR)]): .2f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df["car_minus_min_alt_mode_duration"].abs() <= 15)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum():.2f}%'
    ]
    duration_diff_df["Fastest mode is within 30 minutes of driving"] = [
        f'{len(df[(df["mode"] == Mode.CAR) & (df["car_minus_min_alt_mode_duration"].abs() <= 30)]) / len(df[(df["mode"] == Mode.CAR)]): .2f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df["car_minus_min_alt_mode_duration"].abs() <= 30)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum():.2f}%'
    ]
    st.table(duration_diff_df)
    
    st.header("Geography")
    
    # map of the % of trips in each community regino that can shift given the restrictions
    values = (df.groupby("community")[f"{st.session_state.phase}_shift"].mean()).fillna(0)
    communities = get_communities()
    communities["val"] = values
    
    st.markdown(f"This map shows the % of trips in each community region that can {'feasibly' if st.session_state.phase == Phase.FEASIBLE else 'with likelihood'} shift to any alternative non-car mode.")
    fig0 = px.choropleth(communities, geojson=communities.geometry, locations=communities.index, color="val", color_continuous_scale=["red", "yellow", "green"], range_color=(0, 1), projection="albers usa")
    fig0.update_layout(margin=dict(l=0, r=0, b=0, t=0),
                width=900, 
                height=500,
    )
    fig0.update_geos(fitbounds="locations", visible=False)
    st.plotly_chart(fig0)
    
    # map of % of trips in each community regino that can shift competitively when considering the fastest alternative mode
    df["competitive_timing"] = df["car_minus_min_alt_mode_duration"].abs() <= 15
    values_competitive = (df.groupby("community")["competitive_timing"].mean()).fillna(0)
    communities["val_comp"] = values_competitive
    
    st.markdown(f"This map shows the % of trips in each community region that can competitively shift (maximum bidirectional difference of 15 minutes) to the fastest alternative non-car mode.")
    fig1 = px.choropleth(communities, geojson=communities.geometry, locations=communities.index, color="val_comp", color_continuous_scale=["red", "yellow", "green"], range_color=(0, 1), projection="albers usa")
    fig1.update_layout(margin=dict(l=0, r=0, b=0, t=0),
                width=900, 
                height=500,
    )
    fig1.update_geos(fitbounds="locations", visible=False)
    st.plotly_chart(fig1)
    
    st.header("Raw metrics")
    
    st.markdown(inspect.cleandoc(
        f"""- Total number of person trips on car before applying mode shifts: **{len(df[df['mode'] == Mode.CAR]):,}**
            - Total number of person trips on car after applying mode shifts: **{len(df[(df['mode'] == Mode.CAR) & (~df[f'{st.session_state.phase}_shift'])]):,}**"""
        )
    )
    
    st.text("")
    
    st.markdown(inspect.cleandoc(
        f"""- Total number of person trips on car before applying mode shifts: **{round(df[df['mode'] == Mode.CAR]['vehicle_trips'].sum()):,}**
            - Total number of person trips on car after applying mode shifts: **{round(df[(df['mode'] == Mode.CAR) & (~df[f'{st.session_state.phase}_shift'])]['vehicle_trips'].sum()):,}**"""
        )
    )
    
    st.text("")
    
    st.markdown(inspect.cleandoc(
        f"""- Total VMT before applying {st.session_state.phase} mode shift: **{round(df[df['mode'] == Mode.CAR]['vmt'].sum()):,}**
        - Total VMT after applying {st.session_state.phase} mode shift: **{round(df[(df['mode'] == Mode.CAR) & (~df[f'{st.session_state.phase}_shift'])]['vmt'].sum()):,}**"""
        )
    )
    
    st.text("")
    
    with st.spinner("Running cold start logic"):
        before_cold_starts = df[df["mode"] == Mode.CAR].groupby(["wave", "person_id", "travel_date"]).apply(lambda x: get_num_cold_starts(list(x["depart_time"]), x["duration"].values, list(x["mode"]))).sum()
        after_cold_starts = df[(df['mode'] == Mode.CAR) & (~df[f'{st.session_state.phase}_shift'])].groupby(['wave', 'person_id', 'travel_date']).apply(lambda x: get_num_cold_starts(list(x["depart_time"]), x["duration"].values, list(x["mode"]))).sum()
        if (~df[f"{st.session_state.phase}_shift"]).sum() == 0:
            after_cold_starts = 0
        
    
    st.markdown(inspect.cleandoc(
        f"""- Number of cold starts before applying {st.session_state.phase} mode shifts: **{before_cold_starts:,}**
            - Number of cold starts after applying {st.session_state.phase} mode shifts: **{after_cold_starts:,}**"""
        )
    )
    
    st.header("Shifts by categories")
    
    st.markdown(r"Below, the % of trips that can shift when segmented by income bracket are shown.")
    
    income_pct = df[df["income_detailed"] != "na"].groupby("income_detailed")[f"{st.session_state.phase}_shift"].mean().reindex(["Under 15,000", "$15,000-$24,999", "$25,000-$34,999", "$35,000-$49,999", "$50,000-$74,999", "$75,000-$99,999", "$100,000-$149,999", "$150,000-$199,999", "$200,000-$249,999", "$250,000 or more"])
    fig1 = px.bar(x=income_pct.index, y=income_pct.values)
    st.plotly_chart(fig1)
    
    st.markdown(r"Below, the % of trips that can shift when segmented by trip purpose are shown.")
              
    purpose_pct = df[df["purpose_cleaned"] != "Missing"].groupby("purpose_cleaned")[f"{st.session_state.phase}_shift"].mean()
    fig2 = px.bar(x=purpose_pct.index, y=purpose_pct.values)
    st.plotly_chart(fig2)
    
    st.markdown(r"Below, the % of trips that can shift when segmented by person type are shown.")
                
    person_pct = df[df["person_type"] != "na"].groupby("person_type")[f"{st.session_state.phase}_shift"].mean()
    fig3 = px.bar(x=person_pct.index, y=person_pct.values)
    st.plotly_chart(fig3)
    
    st.markdown(r"Below, the % of trips that can shift when segmented by gender are shown.")
    
    gender_pct = df[df["gender_cleaned"] != "Prefer not to answer"].groupby("gender_cleaned")[f"{st.session_state.phase}_shift"].mean()
    fig4 = px.bar(x=gender_pct.index, y=gender_pct.values)
    st.plotly_chart(fig4)
    
    # if handler["save_result"]:
    #     with st.spinner("Exporting to csv"):
    #         df.to_csv("data/feasible_trips.csv")
        
    
def show_step():
    curr: steps.parent_classes.BaseStep = st.session_state["step_class"]
    st.title(curr.get_name())
    
    if curr.is_continuous():
        curr.set_cutoff_mode(st.sidebar.radio("Choose how to set the cutoff", (CutoffMode.PCT, CutoffMode.RAW)))
        if curr.get_cutoff_mode() == CutoffMode.PCT:
            curr.set_cutoff(st.sidebar.slider("Select a value:", 0.0, 1.0, 0.95, 0.01))
        elif curr.get_cutoff_mode() == CutoffMode.RAW:
            extrema = curr.get_extrema()
            curr.set_cutoff(st.sidebar.slider("Select a value:", float(extrema[0]), float(extrema[1]), float(extrema[1]), float((extrema[1] - extrema[0]) / 100)))
        else:
            raise RuntimeError("something went wrong")
        st.sidebar.markdown(f"Cutoff equivalent: {curr.get_cutoff_equivalent():.2f}")
    
    if st.sidebar.button("Disable step", use_container_width=True):
        curr.disable()
        
    if st.sidebar.button("Apply step", use_container_width=True):
        curr.apply_step()
        curr.show_step_streamlit()
    else:
        st.header("Click the apply step button once the desired settings have been set or click disable to disable the step.")
    

def run():
    st.sidebar.header("Actions")
    option_slot = st.sidebar.empty()

    if st.sidebar.button("Finish and move to summary"):
        st.session_state.in_summary = True
        st.experimental_rerun()
    
    if st.session_state.phase == Phase.FEASIBLE:
        option = option_slot.selectbox("Choose the step you want to run.", st.session_state["feasible_steps"])
    elif st.session_state.phase == Phase.PROBABLE:
        option = option_slot.selectbox("Choose the step you want to run.", st.session_state["probable_steps"])
    else:
        print(st.session_state.phase)
        raise RuntimeError("Something went wrong with the overall step session state variable")
    
    if st.sidebar.button("Refresh"):
        st.experimental_rerun()

    if st.session_state.step != option:
        st.session_state.step = option
        if option in st.session_state.step_class_dict:
            st.session_state.step_class = st.session_state.step_class_dict[option]
        else:
            st.session_state.step_class_dict[option] = getattr(st.session_state.overall_step, option)(st.session_state.df)
            st.session_state.step_class = st.session_state.step_class_dict[option]
    show_step()
    
    d = {}
    for name, step in st.session_state.step_class_dict.items():
        if step.get_previous_run() != None:
            prev = step.get_previous_run()
            if step.is_continuous():
                if prev[1] == CutoffMode.PCT:
                    d[name] = f"{prev[0] * 100:.0f}th pct"
                elif prev[1] == CutoffMode.RAW:
                    d[name] = f"{prev[0]:.2f} units"
                else:
                    raise RuntimeError("Something went wrong with the cutoff mode enum")
            else:
                d[name] = "1"
    
    with st.sidebar.expander("See previously run steps"):
        st.write(d)
    
    st.sidebar.markdown("To export this page to PDF, click the x button above to dismiss the sidebar, and then manually print to PDF")
    

if __name__ == "__main__":
    if "finish_start" not in st.session_state:
        start_screen()
    elif "df" not in st.session_state:
        setup_inputs()
        st.experimental_rerun()
    elif st.session_state.in_summary:
        final_summary()
    else:
        run()

    