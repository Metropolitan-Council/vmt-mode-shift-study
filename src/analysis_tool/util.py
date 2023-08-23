import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from steps.enums import Mode, Phase
from settings import handler

def convert_to_minutes(temp: str) -> float:
        return int(temp[0:2]) * 60 + int(temp[3:5]) + int(temp[6:8]) / 60

def get_num_cold_starts(depart_time: list[str], leg_durations: 'np.ndarray[float]', modes: list[str]):

    leg_starts = np.fromiter((map(convert_to_minutes, depart_time)), dtype=np.float32)
    ref = leg_starts[0]
    # start times, starting by 0 and accounting for midnight wraparound with the mod function, for each leg of the complete tour
    leg_starts = (leg_starts - ref) % 1440
    # calculate end times relative to the start times using the duration category
    leg_ends = leg_starts + leg_durations
    
    cold_starts = 0
    prev_end = -1
    # iterate over all trips in a complete tour
    for i in range(len(leg_starts)):
        # if the current leg mode i car
        if modes[i] == Mode.CAR:
            # if there wasn't a previous or the difference between the end of the last car trip and the beginning of this car trip is more than 15 minutes, it is a cold start
            if prev_end == -1 or leg_starts[i] - leg_ends[i] > 15:
                cold_starts += 1
            # update previous end of car trip
            prev_end = leg_ends[i]
    return cold_starts            


clist = [(0, "red"), (0.5, "yellow"), (1, "green")]
rvb = mcolors.LinearSegmentedColormap.from_list("", clist)

def add_value_labels(ax, spacing=5):
    """Add labels to the end of each bar in a bar chart.

    Arguments:
        ax (matplotlib.axes.Axes): The matplotlib object containing the axes
            of the plot to annotate.
        spacing (int): The distance between the labels and the bars.
    """

    # For each bar: Place a label
    for rect in ax.patches:
        # Get X and Y placement of label from rect.
        y_value = rect.get_height()
        x_value = rect.get_x() + rect.get_width() / 2

        # Number of points between bar and label. Change to your liking.
        space = spacing
        # Vertical alignment for positive values
        va = 'bottom'

        # If value of bar is negative: Place label below bar
        if y_value < 0:
            # Invert space to place label below
            space *= -1
            # Vertically align label at top
            va = 'top'

        # Use Y value as label and format number with one decimal place
        label = "{:.3f}".format(y_value)

        # Create annotation
        ax.annotate(
            label,                      # Use `label` as label
            (x_value, y_value),         # Place label at end of the bar
            xytext=(0, space),          # Vertically shift label by `space`
            textcoords="offset points", # Interpret `xytext` as offset in points
            ha='center',                # Horizontally center label
            va=va)                      # Vertically align label differently for
                                        # positive and negative values.
                                        
def stacked_shift_histogram(df: pd.DataFrame, mode: Mode, mode_duration: str, mode_feasible_field: str):
    df.loc[:, "curr"] = (df[mode_duration] - df["car_duration_seconds_adj"] / 60)
    df.loc[:, "Category"] = "na"
    df.loc[:, "Category"] = np.where(df["mode"] == mode, f"{mode.capitalize()} Trips", df["Category"])
    df.loc[:, "Category"] = np.where((df["mode"] == Mode.CAR) & (df[mode_feasible_field]), "Drive Trips - Feasible to Switch", df["Category"])
    df.loc[:, "Category"] = np.where((df["mode"] == Mode.CAR) & (~df[mode_feasible_field]), "Drive Trips - Not Feasible to Switch", df["Category"])
    view = df[df["Category"] != "na"]
    
    colors_dict = {
        f"{mode.capitalize()} Trips": "#FF2B2B",
        "Drive Trips - Feasible to Switch": "#83C9FF",
        "Drive Trips - Not Feasible to Switch": "#0068C9"
    }
    
    plotly_colors = [colors_dict[c] for c in view["Category"].unique()]
    
    fig = px.histogram(view, x="curr", color="Category", barmode="stack", range_x=[-30,120],
                       labels={"curr": "Travel Time Difference (Alternative Time - Drive Time, minutes)"},
                       color_discrete_sequence=plotly_colors, title=f"Stacked histogram of duration difference between equivalent {mode} and driving trips")
    
    return fig

def get_summary_df(df: pd.DataFrame, steps: list, mode: Mode, mode_feasible_col: str) -> pd.DataFrame:
    res = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    for step in steps:
        if step.get_mode() == mode:
            stats = step.get_step_statistics()
            res[step.get_name()] = [f"{stats[2][0] * 100: .2f}%", f"{stats[2][1] * 100: .2f}%"]
    res["Feasible Across All Criteria"] = [
        f"{len(df[(df['mode'] == Mode.CAR) & df[mode_feasible_col]]) / len(df[df['mode'] == Mode.CAR]) * 100:.2f}%",
        f"{df[(df['mode'] == Mode.CAR) & df[mode_feasible_col]]['vmt'].sum() / df[df['mode'] == Mode.CAR]['vmt'].sum() * 100:.2f}%"
    ]
    
    return res

def get_duration_diff_df(df: pd.DataFrame, mode: Mode, mode_duration: str) -> pd.DataFrame:
    res = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    df.loc[:, "curr"] = (df[mode_duration] - df["car_duration_seconds_adj"] / 60).abs()
    res[f"{mode.capitalize()} is within 5 minutes of driving"] = [
        f'{len(df[(df["mode"] == Mode.CAR) & (df["curr"] <= 5)]) / len(df[(df["mode"] == Mode.CAR)]) * 100: .2f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df["curr"] <= 5)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.2f}%'
    ]
    res[f"{mode.capitalize()} is within 15 minutes of driving"] = [
        f'{len(df[(df["mode"] == Mode.CAR) & (df["curr"] <= 15)]) / len(df[(df["mode"] == Mode.CAR)]) * 100: .2f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df["curr"] <= 15)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.2f}%'
    ]
    res[f"{mode.capitalize()} is within 30 minutes of driving"] = [
        f'{len(df[(df["mode"] == Mode.CAR) & (df["curr"] <= 30)]) / len(df[(df["mode"] == Mode.CAR)]) * 100: .2f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df["curr"] <= 30)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.2f}%'
    ]
    return res
                                        
def stateful_button(*args, key=None, **kwargs):
    """
    Works just like a normal streamlit button, but it remembers its state, so that
    it works as a toggle button. If you click it, it will be pressed, and if you click
    it again, it will be unpressed.

    args:
        Same as st.button
    kwargs:
        Same as st.button except key is required
    """

    if key is None:
        raise ValueError("Must pass key")

    if key not in st.session_state:
        st.session_state[key] = False

    if "type" not in kwargs:
        kwargs["type"] = "primary" if st.session_state[key] else "secondary"

    if st.sidebar.button(*args, **kwargs):
        st.session_state[key] = not st.session_state[key]
        st.experimental_rerun()

    return st.session_state[key]

def bigger_markdown(x: str) -> str:
    for line in x.split("\n"):
        st.markdown(f'<p class="bigger-font">{line}</p>', unsafe_allow_html=True)