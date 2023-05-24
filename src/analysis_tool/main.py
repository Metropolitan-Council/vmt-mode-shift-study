import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import inspect

import steps
from initialize import prepare_csv
from settings import handler, get_communities
from steps.mode_enum import Mode

if "df" not in st.session_state:
    if handler["force_reinitialize"]:
        with st.spinner(text="Building the input data"):
            raw = pd.read_csv(handler["drive_data_dir"] + "/data_processed/tbi_cleaned.csv")

            df = prepare_csv(raw, handler["drive_data_dir"])
    else:
        try:
            df = pd.read_csv("data/" + handler["tbi_file_name"])
            
        except Exception as e:
            with st.spinner(text="Building the input data"):
                
                raw = pd.read_csv(handler["drive_data_dir"] + "/data_processed/tbi_cleaned.csv")

                df = prepare_csv(raw, handler["drive_data_dir"])
    
    st.session_state["df"] = df
    st.session_state["step"] = "WalkDistanceStep"
    st.session_state["overall_step"] = steps.feasible_steps
    st.session_state["step_class"] = steps.feasible_steps.WalkDistanceStep(df)
    st.session_state["percentiles"] = dict()
    
def get_num_cold_starts(chunk):
    def convert_to_minutes(str):
        hours, minutes, seconds = [int(x) for x in str.split(":")]
        return hours * 60 + minutes + seconds / 60
    
    leg_starts = chunk["depart_time"].apply(lambda x: convert_to_minutes(x)).values
    ref = leg_starts[0]
    # start times, starting by 0 and accounting for midnight wraparound with the mod function, for each leg of the complete tour
    leg_starts = [(x - ref) % 1440 for x in chunk["depart_time"].apply(lambda x: convert_to_minutes(x)).values]
    leg_durations = chunk["duration"].values
    # calculate end times relative to the start times using the duration category
    leg_ends = [(x + y) for (x, y) in zip(leg_starts, leg_durations)]
    modes = chunk["mode"].values
    
    cold_starts = 0
    prev_end = -1
    # iterate over all trips in a complete tour
    for i in range(len(leg_starts)):
        # if the current leg mode i car
        if modes[i] == Mode.CAR:
            # if there wasn't a previous or the difference between the end of the last car trip and the beginning of this car trip is more than 15 minutes, it is a cold start
            if prev_end == -1 or leg_starts[i] - leg_ends[i] > handler["cold_start_threshold"]:
                cold_starts += 1
            # update previous end of car trip
            prev_end = leg_ends[i]
    return cold_starts  
    
def final_summary():
    st.title("Summary")
    
    df = st.session_state.df
    df.loc[:, "feasible_shift"] = (
        df["feasible_transit_shift"] | 
        df["feasible_walk_shift"] | 
        df["feasible_bike_shift"]
    )
    
    st.markdown(f"Percent of car trips that can feasibly/with likelihood shift to a non-car mode: **{df[df['mode'] == Mode.CAR]['feasible_shift'].sum() / len(df[df['mode'] == Mode.CAR])}**")
    
    values = (df.groupby("community")["feasible_shift"].mean()).fillna(0)
    communities = get_communities()
    communities["val"] = values
    
    st.markdown(r"This map shows the % of trips in each community region that can feasibly shift to any alternative non-car mode.")
    fig = px.choropleth(communities, geojson=communities.geometry, locations=communities.index, color="val", color_continuous_scale=["red", "yellow", "green"], range_color=(0, 1))
    fig.update_layout(margin=dict(l=0, r=0, b=0, t=0),
                width=900, 
                height=500,
    )
    fig.update_geos(fitbounds="locations", visible=False)
    st.plotly_chart(fig)
    
    st.markdown(inspect.cleandoc(
        f"""- Total number of person trips on car before applying mode shifts: **{len(df[df['mode'] == Mode.CAR])}**
            - Total number of person trips on car after applying mode shifts: **{len(df[(df['mode'] == Mode.CAR) & (~df['feasible_shift'])])}**"""
        )
    )
    
    st.text("")
    
    st.markdown(inspect.cleandoc(
        f"""- Total number of person trips on car before applying mode shifts: **{df[df['mode'] == Mode.CAR]['vehicle_trips'].sum()}**
            - Total number of person trips on car after applying mode shifts: **{df[(df['mode'] == Mode.CAR) & (~df['feasible_shift'])]['vehicle_trips'].sum()}**"""
        )
    )
    
    st.text("")
    
    st.markdown(inspect.cleandoc(
        f"""- Total VMT before applying feasible mode shift: **{df[df['mode'] == Mode.CAR]['vmt'].sum()}**
        - Total VMT after applying feasible mode shift: **{df[(df['mode'] == Mode.CAR) & (~df['feasible_shift'])]['vmt'].sum()}**"""
        )
    )
    
    st.text("")
    
    with st.spinner("Running cold start logic..."):
        temp = df[df["mode"] == Mode.CAR].groupby(["wave", "person_id", "travel_date"]).apply(lambda x: get_num_cold_starts(x))
    
    st.markdown(inspect.cleandoc(
        f"""- Number of cold starts before applying feasible mode shifts: **{temp.sum()}**
            - Number of cold starts after applying feasible mode shifts: **{
                df[(df['mode'] == Mode.CAR) & (~df['feasible_shift'])].groupby(['wave', 'person_id', 'travel_date']).apply(lambda x: get_num_cold_starts(x)).sum()
            }**"""
        )
    )
    
    
    with st.spinner("Exporting to csv..."):
        df.to_csv("data/feasible_trips.csv")
    
    
def show_step():
    curr = st.session_state["step_class"]
    st.title(curr.get_name())
    
    if curr.is_continuous():
        value = st.sidebar.slider("Select a value:", 0.0, 1.0, 0.95, 0.01)
        curr.set_cutoff(value)
        st.sidebar.markdown(f"Cutoff: {curr.get_cutoff_numerical()}")
    
    if st.sidebar.button("Disable step"):
        curr.disable()
    else:
        curr.apply_step()
        
    text = curr.get_text()
    
    st.markdown(text[0])
    st.text("")
    
    slots = []
    
    for section in text[1:]:
        st.markdown(section)
        temp = st.empty()
        slots.append(temp)
        
    slots[0].pyplot(curr.get_summary_figure()[0])
    slots[1].dataframe(curr.get_summary_statistics())
    slots[2].plotly_chart(curr.get_map())
    

def run():
    st.sidebar.header("Actions")
    option_slot = st.sidebar.empty()
    if st.sidebar.button("Finish and move to summary"):
        final_summary()
        return
    
    option = option_slot.selectbox("Choose the step you want to run.", handler["feasible_steps"])
    
    if st.sidebar.button("Refresh"):
        st.experimental_rerun()
        
    if st.session_state.step != option:
        st.session_state.percentiles[st.session_state.step_class.get_name()] = st.session_state.step_class.get_cutoff()
        st.session_state.step = option
        st.session_state.step_class = getattr(st.session_state.overall_step, option)(st.session_state.df)
        
    show_step()
    
    st.sidebar.markdown("To export this page to PDF, click the x button above to dismiss the sidebar, and then manually print to PDF")
    

if __name__ == "__main__":
    run()

    