import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import inspect
import matplotlib.pyplot as plt

import steps
from initialize import prepare_csv
from settings import handler, get_communities
from steps.mode_enum import Mode
from util import get_num_cold_starts, add_value_labels, rvb

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
    
def final_summary():
    st.title("Summary")
    
    st.markdown("Below are the set percentiles for each step (if it is -1, it is not applicable--either disabled/not set or categorical).")
    st.write(st.session_state.percentiles)
    
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
    fig = px.choropleth(communities, geojson=communities.geometry, locations=communities.index, color="val", color_continuous_scale=["red", "yellow", "green"], range_color=(0, 1), projection="albers usa")
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
    
    with st.spinner("Running cold start logic"):
        before_cold_starts = df[df["mode"] == Mode.CAR].groupby(["wave", "person_id", "travel_date"]).apply(lambda x: get_num_cold_starts(x)).sum()
        after_cold_starts = df[(df['mode'] == Mode.CAR) & (~df['feasible_shift'])].groupby(['wave', 'person_id', 'travel_date']).apply(lambda x: get_num_cold_starts(x)).sum()
        if (~df["feasible_shift"]).sum() == 0:
            after_cold_starts = 0
        
    
    st.markdown(inspect.cleandoc(
        f"""- Number of cold starts before applying feasible mode shifts: **{before_cold_starts}**
            - Number of cold starts after applying feasible mode shifts: **{after_cold_starts}**"""
        )
    )
    
    st.markdown(r"Below, the % of trips that can shift when segmented by income bracket are shown.")
    
    income_pct = df.groupby("income_broad")["feasible_shift"].mean().reindex(["Prefer not to answer", "Under $25,000", "$25,000-$49,999", "$50,000-$74,999", "$75,000-$99,999", "$100,000 or more", "$100,000-$199,999", "$200,000 or more"])
    fig1 = px.bar(x=income_pct.index, y=income_pct.values)
    st.plotly_chart(fig1)
    
    st.markdown(r"Below, the % of trips that can shift when segmented by trip purpose are shown.")
              
    purpose_pct = df.groupby("d_purpose_category")["feasible_shift"].mean()
    fig2 = px.bar(x=purpose_pct.index, y=purpose_pct.values)
    st.plotly_chart(fig2)
    
    df["child"] = df["age"].isin(["5-15", "5 to 15", "16-17", "16 to 17", "Under 5"])
    df["senior"] = df["age"].isin(["65-74", "65 to 74", "75 or older", "75 to 84", "85 or older"])
    df["student"] = ~df["student_status"].str.contains("No")
    df["unemployed"] = df["job_type"].str.contains("Missing")
    df["parent"] = df["num_kids"] != 0
        
    df["person_type"] = "na"
    df["person_type"] = np.where(df["child"], "child", df["person_type"])
    df["person_type"] = np.where((~df["child"]) & (df["student"]), "college student", df["person_type"])
    df["person_type"] = np.where(~df["unemployed"] & df["parent"], "working adult with kids", df["person_type"])
    df["person_type"] = np.where(df["unemployed"] & df["parent"], "non-working adult with kids", df["person_type"])
    df["person_type"] = np.where(~df["unemployed"] & ~df["parent"], "working adult without kids", df["person_type"])
    df["person_type"] = np.where(df["unemployed"] & ~df["parent"], "non-working adult without kids", df["person_type"])
    df["person_type"] = np.where(df["senior"] & df["unemployed"], "retired", df["person_type"])
    
    st.markdown(r"Below, the % of trips that can shift when segmented by person type are shown.")
                
    person_pct = df[df["person_type"] != "na"].groupby("person_type")["feasible_shift"].mean()
    fig3 = px.bar(x=person_pct.index, y=person_pct.values)
    st.plotly_chart(fig3)
    
    if handler["save_result"]:
        with st.spinner("Exporting to csv"):
            df.to_csv("data/feasible_trips.csv")
        
    
def show_step():
    curr = st.session_state["step_class"]
    st.title(curr.get_name())
    
    if curr.is_continuous():
        value = st.sidebar.slider("Select a value:", 0.0, 1.0, 0.95, 0.01)
        curr.set_cutoff(value)
        st.sidebar.markdown(f"Cutoff: {curr.get_cutoff_numerical():.2f}")
    
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
    st.session_state.percentiles[st.session_state.step_class.get_name()] = st.session_state.step_class.get_cutoff()
    
    st.sidebar.header("Actions")
    option_slot = st.sidebar.empty()
    if st.sidebar.button("Finish and move to summary"):
        
        final_summary()
        return
    
    option = option_slot.selectbox("Choose the step you want to run.", handler["feasible_steps"])
    
    if st.sidebar.button("Refresh"):
        st.experimental_rerun()
        
    if st.session_state.step != option:
        st.session_state.step = option
        st.session_state.step_class = getattr(st.session_state.overall_step, option)(st.session_state.df)
        
    show_step()
    
    st.sidebar.markdown("To export this page to PDF, click the x button above to dismiss the sidebar, and then manually print to PDF")
    

if __name__ == "__main__":
    run()

    