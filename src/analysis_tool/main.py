import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import keyring

from initialize import prepare_csv

import pandas as pd
import steps

from settings import handler

if "df" not in st.session_state:
    try:
        df = pd.read_csv("data/tbi_full.csv")
        
    except Exception as e:
        raw = pd.read_csv(handler["drive_data_dir"] + "/data_processed/feasible_shifts.csv")

        df = prepare_csv(raw, handler["drive_data_dir"])
    
    st.session_state["df"] = df
    st.session_state["step"] = "WalkDistanceStep"
    st.session_state["overall_step"] = steps.feasible_steps
    
def show_step(step):
    
    if st.session_state.step.is_continuous():
        value = st.sidebar.slider("Select a value:", 0.0, 1.0, 0.95, 0.01)
        st.session_state.step.set_cutoff(value)
    
    
    if st.sidebar.button("Disable step"):
        st.session_state.step.disable()
    else:
        st.session_state.step.apply_step()
    temp = st.session_state.step.get_map()
    
    st.dataframe(st.session_state.step.get_summary_statistics())
    st.pyplot(st.session_state.step.get_summary_figure()[0])
    st.plotly_chart(temp)
    st.text(st.session_state.step.get_step_statistics())
    
def SequentialMode(step):
    pass

def FreeformMode(step):
    pass

if __name__ == "__main__":
    
    if "settings" not in st.session_state:
        mode = st.radio("Choose the mode for the tool", ("Sequential", "Freeform"))
        if st.button("Start tool"):
            st.session_state["settings"] = True
            st.session_state["mode"] = mode
            
    else:
        step = getattr(st.session_state["overall_step"], st.session_state["step"])
        
        
    x = getattr(steps.feasible_steps, "WalkDistanceStep")
    
    if "step" not in st.session_state:
        st.session_state["step"] = x(st.session_state.df)

    