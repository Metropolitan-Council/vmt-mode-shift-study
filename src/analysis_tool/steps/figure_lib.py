import pandas as pd
import itertools
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import plotly.express as px
import logging

from steps.enums import Mode

def show_summaries(df: pd.DataFrame, modes, percentile=[0.95], column_names=None) -> pd.DataFrame: # show normal summaries for each mode side by side
    """
    This function shows the summaries for 2+ modes side-by-side in a dataframe

    Args:
        df (pd.DataFrame): the dataframe we are working with
        modes (list[tuple]): the modes to include in the comparison dataframe and their associated column (list of tuples)
        percentile (list, optional): the percentiles to add to the normal quartiles. Defaults to [0.95].
        column_names (list[str], optional): what to call the columns in the output dataframe. Defaults to None.

    Returns:
        _type_: _description_
    """
    # initial setup
    res = []
    labels = []
    
    # add percentile to the list of quartiles and prevent duplicates
    if type(percentile) != type([]):
        percentile = [percentile]
    p = [0.25, 0.5, 0.75]
    p += percentile
    p = list(set(p))
    
    # for each mode, append the summary statistics to the res array
    for m in modes:        
        mode = m[0]
        column = m[1]
        labels.append(mode + ' ' + column)
        
        group = df[df["mode"] == mode]
        res.append(group[column].describe(percentiles=p))
        
    # concat all the summary statistics
    x = pd.concat(res, axis=1)
    
    # try to set the column names to the target; otherwise, use default naming convention
    if column_names != None and len(x.columns) == len(column_names):
        x.columns = column_names
    else:
        if column_names != None:
            logging.warning("Passed in column names does not match the summary dataframe -- resorting to default naming convention")
        x.columns = [' '.join(col_name.replace(" ", ":_").split("_")).capitalize() for col_name in labels]
        x.index = x.index.str.capitalize()
    return x

def show_value_counts(df: pd.DataFrame, modes: list) -> pd.DataFrame:
    """
    This function shows the value counts of several modes side-by-side. 

    Args:
        df (pd.DataFrame): the dataframe we are working with
        modes (list): a collection of (mode, column) that we want to consider value counts for

    Returns:
        pd.DataFrame: the dataframe showing the side-by-side value counts
    """
    # setup res/labels (column names)
    res = []
    labels = []
    
    # for each mode/column pair in modes, append the corresponding value counts
    for m in modes:        
        mode = m[0]
        column = m[1]
        labels.append(mode + ' ' + column)
        
        group = df[df["mode"] == mode]
        res.append(group[column].value_counts())
        
    # concat the value counts together, rename the columns, and return
    x = pd.concat(res, axis=1)
    x.columns = labels
    return x

def plot_mode_density(df: pd.DataFrame, modes, percentile=0.95, size=(12, 6), bins=300, function=lambda x: x):
    """
    This function returns a density plot/histogram for various mode/column combinations overlaid on one another.

    Args:
        df (pd.DataFrame): the intenral dataframe we are working with for information retrieval
        modes (list[tuple]): a collections of mode, column pairs
        percentile (float, optional): the percnetile to have a vertical line delineating. Defaults to 0.95.
        size (tuple, optional): size of the output figure. Defaults to (12, 6).
        bins (int, optional): number of bins in the histogram. Defaults to 300.
        function (lambda, optional): how to transform the values. Defaults to lambdax:x.

    Returns:
        MatPlotLib fig/axes: the desired figure
    """
    palette = itertools.cycle(sns.color_palette()) # cycle through colors to make sure each mode gets a unique one
    fig, ax = plt.subplots(figsize=size)
    for m in modes: # cycle through all mode/column pairs
        mode = m[0]
        column = m[1]
        label = mode + ' ' + column
        
        c = next(palette) # get color to use
        group = df[df["mode"] == mode] # filter out everything but the current mode
        sns.histplot(np.random.choice(function(group[column]), 10000), ax=ax, stat="density", kde=True, label=label, color=c, bins=bins) # plot hist plot with kde overlayed in the color
        val = function(group[column]).quantile(q=percentile) # calculate the value of the given percentile (default 0.95)
        plt.axvline(x=val, color=c) # plot line representing that value on the plot        
        plt.legend()
    return fig, ax

def plot_density_plotly(df: pd.DataFrame, alt_mode: str, column: str, cutoff: float):
    """
    This function returns the density plot where car/alt mode plots of some column are overlaid. 

    Args:
        df (pd.DataFrame): the internal dataframe we are working with
        alt_mode (str): the other mode we are considering (we will always compare with car)
        column (str): the name of the column in df that is being considered
        cutoff (float): the percentile at which to draw a vertical line for delineation

    Returns:
        go.Figure: plotly object
    """
    # create histogram with the desired modes and with the desired column on the x-axis
    fig = px.histogram(
        df[df["mode"].isin([alt_mode, Mode.CAR])], 
        x=column, 
        color="mode", 
        barmode="overlay",
        color_discrete_sequence=["orange", "blue"],
        histnorm="probability density"
    )
    
    # add two percentile lines -- one for each mode
    fig.add_vline(
        x=df[df["mode"] == Mode.CAR][column].quantile(q=cutoff), 
        line_color="orange", 
        line_dash="dash"
    )
    fig.add_vline(
        x=df[df["mode"] == alt_mode][column].quantile(q=cutoff), 
        line_color="blue", 
        line_dash="dash"
    )

    # add annotation for user-frinedliness
    fig.add_annotation(dict(font=dict(color='black',size=15),
                                            x=0,
                                            y=-0.25,
                                            showarrow=False,
                                            text="To select a subset of the histogram, drag and drop. To zoom back to default, double click.",
                                            textangle=0,
                                            xanchor='left',
                                            xref="paper",
                                            yref="paper"))
    
    return fig

def plot_multi_barplot(df: pd.DataFrame, x: str, y: str, figsize=(7, 5), order=None):
    
    # plot normalized bar plot of the values in each mode side by side
    fig, ax = plt.subplots(figsize=figsize)
    if y == "mode": 
        df = df[df["mode"].isin(Mode.get_all())]
    (df
     .groupby(y)[x]
     .value_counts(normalize=True)
     .mul(100)
     .rename("percent")
     .reset_index()
     .pipe((sns.barplot, "data"), x=x, y="percent", hue=y, ax=ax, order=order)
    )
    
    return fig, ax

