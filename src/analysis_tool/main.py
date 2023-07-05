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
from util import get_num_cold_starts, add_value_labels, rvb
import json

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
    
    st.session_state["df"] = df
    st.session_state["step"] = "WalkDistanceStep"
    st.session_state["phase"] = Phase.FEASIBLE
    st.session_state["overall_step"] = steps.feasible_steps
    st.session_state["step_class_dict"] = dict()
    st.session_state["step_class_dict"]["WalkDistanceStep"] = steps.feasible_steps.WalkDistanceStep(df)
    st.session_state["step_class"] = st.session_state["step_class_dict"]["WalkDistanceStep"]
    st.session_state["in_summary"] = False
    
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
    
    print("probable setup")
    
    return 0
    
def final_summary():
    if st.session_state.phase == Phase.FEASIBLE:
        if st.sidebar.button("Move to probable step"):
            setup_probable()
            st.experimental_rerun()
    
    df: pd.DataFrame = st.session_state.df
    
    if st.sidebar.button("Save current result to csv"):
        with st.spinner("Exporting dataframe and percentiles"):
            df.to_csv(f"output/{st.session_state.phase}_trips.csv")
            f = open(f"output/{st.session_state.phase}_percentiles.json", "w")
            f.write({step_name: step_class.get_cutoff() for step_name, step_class in st.session_state.step_class_dict.items()})
            f.close()
    
    st.title("Summary")
    
    st.markdown("Below are the set percentiles for each step (if it is -1, it is not applicable--either disabled/not set or categorical).")
    st.write({step_name: step_class.get_cutoff() for step_name, step_class in st.session_state.step_class_dict.items()})
    
    df.loc[:, f"{st.session_state.phase}_shift"] = (
        df[f"{st.session_state.phase}_transit_shift"] | 
        df[f"{st.session_state.phase}_walk_shift"] | 
        df[f"{st.session_state.phase}_bike_shift"]
    )
    
    st.markdown(f"Percent of car trips that can  {'feasibly' if st.session_state.phase == Phase.FEASIBLE else 'with likelihood'} shift to a non-car mode: **{df[df['mode'] == Mode.CAR][f'{st.session_state.phase}_shift'].sum() / len(df[df['mode'] == Mode.CAR]) * 100:.2f}%**")
    
    if st.session_state.phase == Phase.FEASIBLE:
        st.session_state["feasible_pct"] = df[df['mode'] == Mode.CAR][f'{st.session_state.phase}_shift'].sum() / len(df[df['mode'] == Mode.CAR])
    
    values = (df.groupby("community")[f"{st.session_state.phase}_shift"].mean()).fillna(0)
    communities = get_communities()
    communities["val"] = values
    
    st.markdown(r"This map shows the % of trips in each community region that can {'feasibly' if st.session_state.phase == Phase.FEASIBLE else 'with likelihood'} shift to any alternative non-car mode.")
    fig = px.choropleth(communities, geojson=communities.geometry, locations=communities.index, color="val", color_continuous_scale=["red", "yellow", "green"], range_color=(0, 1), projection="albers usa")
    fig.update_layout(margin=dict(l=0, r=0, b=0, t=0),
                width=900, 
                height=500,
    )
    fig.update_geos(fitbounds="locations", visible=False)
    st.plotly_chart(fig)
    
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
    
    st.markdown(r"Below, the distribution of the duration difference between the best non-car mode and car for shifted trips is shown")
    df["transit_duration_seconds_na"] = df["transit_duration"].fillna(9999999) * 60
    df["min_alt_mode_duration"] = df[["transit_duration_seconds_na", "bike_duration_seconds_adj", "walk_duration_seconds"]].min(axis=1)
    df["car_minus_min_alt_mode_duration"] = (df["car_duration_seconds_adj"] - df["min_alt_mode_duration"]) / 60
    
    fig5 = px.histogram(df, x="car_minus_min_alt_mode_duration")
    st.plotly_chart(fig5)
    
    # if handler["save_result"]:
    #     with st.spinner("Exporting to csv"):
    #         df.to_csv("data/feasible_trips.csv")
        
    
def show_step():
    curr: steps.parent_classes.BaseStep = st.session_state["step_class"]
    st.title(curr.get_name())
    
    if curr.is_continuous():
        continuous_opt = st.sidebar.radio("Choose how to set the cutoff", (CutoffMode.PCT, CutoffMode.RAW), key=st.session_state.step + st.session_state.phase + "radio")
        curr.set_cutoff_mode(continuous_opt)
        if continuous_opt == CutoffMode.PCT:
            value = st.sidebar.slider("Select a value:", 0.0, 1.0, float(curr.get_cutoff()), 0.01, key=st.session_state.step + st.session_state.phase + "pct_slider")
        elif continuous_opt == CutoffMode.RAW:
            extrema = curr.get_extrema()
            value = st.sidebar.slider("Select a value:", float(extrema[0]), float(extrema[1]), float(extrema[1]), float((extrema[1] - extrema[0]) / 100), key=st.session_state.step + st.session_state.phase + "raw_slider")
        else:
            raise RuntimeError("something went wrong")
        curr.set_cutoff(value)
        st.sidebar.markdown(f"Cutoff equivalent: {curr.get_cutoff_equivalent():.2f}")
    
    if st.sidebar.button("Disable step"):
        curr.disable()
    else:
        curr.apply_step()
        
    curr.show_step_streamlit()
    

def run():
    st.sidebar.header("Actions")
    option_slot = st.sidebar.empty()

    if st.sidebar.button("Finish and move to summary"):
        st.session_state.in_summary = True
        st.experimental_rerun()
    
    if st.session_state.phase == Phase.FEASIBLE:
        option = option_slot.selectbox("Choose the step you want to run.", handler["feasible_steps"])
    elif st.session_state.phase == Phase.PROBABLE:
        option = option_slot.selectbox("Choose the step you want to run.", handler["probable_steps"])
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
    
    st.sidebar.markdown("To export this page to PDF, click the x button above to dismiss the sidebar, and then manually print to PDF")
    

if __name__ == "__main__":
    if "df" not in st.session_state:
        setup_inputs()
        st.experimental_rerun()
    elif st.session_state.in_summary:
        final_summary()
    else:
        run()

    