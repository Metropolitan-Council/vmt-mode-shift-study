import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import time

from initialize import prepare_csv

import pandas as pd
import steps

if "df" not in st.session_state:
    df = pd.read_csv("data/tbi_full.csv")
    st.session_state["df"] = df
# if "step" not in st.session_state:
#     st.session_state["step"] = "WalkDistanceStep"
# # Sidebar section for the slider

if __name__ == "__main__":
    
    x = getattr(steps.feasible_steps, "WalkDistanceStep")
    
    if "step" not in st.session_state:
        st.session_state["step"] = x(st.session_state.df)

    value = st.sidebar.slider("Select a value:", 0.0, 1.0, 0.95, 0.01)
        
    if st.session_state.step.is_continuous():
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