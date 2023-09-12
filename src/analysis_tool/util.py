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
    """This is a helper function that converts a timestamp string into the number of minutes it is after midnight.

    Args:
        temp (str): A time string in format HH:MM:SS

    Returns:
        float: The number of minutes after midnight temp represents
    """
    return int(temp[0:2]) * 60 + int(temp[3:5]) + int(temp[6:8]) / 60

def get_num_cold_starts(depart_time: list[str], leg_durations: 'np.ndarray[float]', modes: list[str]) -> int:
    """This is a function that calculates the number of cold starts there will be in a given linked trip.

    Args:
        depart_time (list[str]): a list of depart times for each trip in the linked trip
        leg_durations (np.ndarray[float]): a list of durations for each trip in the linked trip
        modes (list[str]): a list of the modes for each trip in the linked trip (these three should correspond to each other)

    Returns:
        int: the number of cold starts that will result from this
    """
    # convert timestamp starts to minutes
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
                                        
def stacked_shift_histogram(df: pd.DataFrame, mode: Mode, mode_duration: str, mode_feasible_field: str, phase: Phase) -> go.Figure:
    """This function creates a stacked shift histogram (as seen in the presentation) given a non-car mode, mode duration column, and mode feasible field.

    Args:
        df (pd.DataFrame): input dataframe
        mode (Mode): non-car mode we are analyzing
        mode_duration (str): column in df that corresponds to the duration (in minutes) of mode
        mode_feasible_field (str): column in df that corresponds to the feasibility/ability to switch
        phase (Phase): the current phase we are in

    Returns:
        go.Figure: The plotly stacked shift histogram (pre-formatted)
    """
    # create temp columns for duration difference & categories (mode trips, drive shifts that can shift, and drive shifts that can't)
    df.loc[:, "curr"] = (df[mode_duration] - df["car_duration_seconds_adj"] / 60)
    df.loc[:, "Category"] = "na"
    df.loc[:, "Category"] = np.where(df["mode"] == mode, f"{mode.capitalize()} Trips", df["Category"])
    df.loc[:, "Category"] = np.where((df["mode"] == Mode.CAR) & (df[mode_feasible_field]), f"Drive Trips - {phase} to Switch", df["Category"])
    df.loc[:, "Category"] = np.where((df["mode"] == Mode.CAR) & (~df[mode_feasible_field]), f"Drive Trips - Not {phase} to Switch", df["Category"])
    
    # only consider non-na trips
    view = df[df["Category"] != "na"]
    
    # map each category to a different color
    colors_dict = {
        f"{mode.capitalize()} Trips": "#FF2B2B",
        f"Drive Trips - {phase} to Switch": "#83C9FF",
        f"Drive Trips - Not {phase} to Switch": "#0068C9"
    }
    
    # use mapping to create a color list for plotly
    plotly_colors = [colors_dict[c] for c in view["Category"].unique()]
    
    # create the stacked histogram
    fig = px.histogram(view, x="curr", y="person_trips", histfunc="sum", color="Category", barmode="stack", range_x=[-20,120],
                       color_discrete_sequence=plotly_colors)
    fig.update_layout(
        title=dict(
            text=f"Stacked histogram of duration difference<br>between equivalent {mode} and driving trips",
            font=dict(
                size=18
            ),
            x=0.5,
            y=0.95,
            xanchor='center',
        ),
        legend=dict(font=dict(size=16)),
        xaxis_title=dict(text="Travel Time Difference (Alternative Time - Drive Time, minutes)", font=dict(size=16)),
        yaxis_title=dict(text="Person Trips", font=dict(size=16))
    )
    
    # return figure
    return fig

def get_summary_df(df: pd.DataFrame, steps: list, mode: Mode, mode_shift_col: str, phase: Phase) -> pd.DataFrame:
    """This function gets the summary table for a given mode, describing the % of car trips/% of VMT that each step (and all steps) apply to.

    Args:
        df (pd.DataFrame): the dataframe used in the tool
        steps (list): a list of the step classes used in the tool
        mode (Mode): the mode to consider
        mode_shift_col (str): the column describing whether it a shift to a mode is likely/feasible

    Returns:
        pd.DataFrame: The desired summary table
    """
    # create output table
    res = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    
    # for each step, if the step applies to the current mode, extract the step statistics
    for step in steps:
        if step.get_mode() == mode:
            stats = step.get_step_statistics()
            res[step.get_name()] = [f"{stats[2][0] * 100: .1f}%", f"{stats[2][1] * 100: .1f}%"]
            
    # calculate statistics for all criteria at once
    res[f"{phase} Across All Criteria"] = [
        f"{df[(df['mode'] == Mode.CAR) & df[mode_shift_col]]['vehicle_trips'].sum() / df[df['mode'] == Mode.CAR]['vehicle_trips'].sum() * 100:.1f}%",
        f"{df[(df['mode'] == Mode.CAR) & df[mode_shift_col]]['vmt'].sum() / df[df['mode'] == Mode.CAR]['vmt'].sum() * 100:.1f}%"
    ]
    
    return res

def get_duration_diff_df(df: pd.DataFrame, mode: Mode, mode_shift_col: str, mode_duration: str) -> pd.DataFrame:
    """This function creates a table detailing various summary statistics (% of car trips/VMT that is in this category) for trips within 5/15/30 minutes of driving given a mode.

    Args:
        df (pd.DataFrame): the dataframe used in the tool
        mode (Mode): the mode to consider
        mode_shift_col (str): the column describing whether it a shift to a mode is likely/feasible
        mode_duration (str): the column name of the column in df that describes the duration of the mode trip (in minutes)

    Returns:
        pd.DataFrame: the desired summary table
    """
    # create initial table
    res = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    # calculate duration difference in temp column
    df.loc[:, "curr"] = (df[mode_duration] - df["car_duration_seconds_adj"] / 60).abs()
    
    # calculate summary statistics for mode trips within 5/15/30 minutes of driving
    res[f"{mode.capitalize()} within 5 minutes of driving"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[mode_shift_col]) & (df["curr"] <= 5)]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[mode_shift_col]) & (df["curr"] <= 5)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%'
    ]
    res[f"{mode.capitalize()} within 15 minutes of driving"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[mode_shift_col]) & (df["curr"] <= 15)]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[mode_shift_col]) & (df["curr"] <= 15)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%'
    ]
    res[f"{mode.capitalize()} within 30 minutes of driving"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[mode_shift_col]) & (df["curr"] <= 30)]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[mode_shift_col]) & (df["curr"] <= 30)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%'
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

def bigger_markdown(x: str) -> None:
    """This function converts the string x into a form that will be a larger font size upon being displayed in stremalit

    Args:
        x (str): the string to display
    """
    
    # for each paragraph in x, output markdown of the paragraph and have it be of the bigger-font class
    for line in x.split("\n"):
        st.markdown(f'<p class="bigger-font">{line}</p>', unsafe_allow_html=True)