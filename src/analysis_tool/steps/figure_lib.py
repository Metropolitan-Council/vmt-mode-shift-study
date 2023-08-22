import pandas as pd
import itertools
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import plotly.express as px

from steps.enums import Mode

def show_summaries(df: pd.DataFrame, modes, percentile=[0.95]): # show normal summaries for each mode side by side
    res = []
    labels = []
    if type(percentile) != type([]):
        percentile = [percentile]
    p = [0.25, 0.5, 0.75]
    p += percentile
    p = list(set(p))
    for m in modes:        
        mode = m[0]
        column = m[1]
        labels.append(mode + ' ' + column)
        
        group = df[df["mode"] == mode]
        res.append(group[column].describe(percentiles=p))
    x = pd.concat(res, axis=1)
    print(labels)
    x.columns = [' '.join(col_name.replace(" ", ":_").split("_")).capitalize() for col_name in labels]
    x.index = x.index.str.capitalize()
    return x

def show_value_counts(df: pd.DataFrame, modes):
    res = []
    labels = []
    for m in modes:        
        mode = m[0]
        column = m[1]
        labels.append(mode + ' ' + column)
        
        group = df[df["mode"] == mode]
        res.append(group[column].value_counts())
    x = pd.concat(res, axis=1)
    x.columns = labels
    return x

def plot_mode_density(df: pd.DataFrame, modes, percentile=0.95, size=(12, 6), bins=300, function=lambda x: x):
    palette = itertools.cycle(sns.color_palette()) # cycle through colors to make sure each mode gets a unique one
    fig, ax = plt.subplots(figsize=size)
    for m in modes: # cycle through all modes
        mode = m[0]
        column = m[1]
        label = mode + ' ' + column
        
        c = next(palette) # get color to use
        group = df[df["mode"] == mode] # filter out the current mode
        sns.histplot(np.random.choice(function(group[column]), 10000), ax=ax, stat="density", kde=True, label=label, color=c, bins=bins) # plot hist plot with kde overlayed in the color
        val = function(group[column]).quantile(q=percentile) # calculate the value of the given percentile (default 0.95)
        plt.axvline(x=val, color=c) # plot line representing that value on the plot        
        plt.legend()
    return fig, ax

def plot_density_plotly(df: pd.DataFrame, alt_mode: str, column: str, cutoff: float):
    fig = px.histogram(
        df[df["mode"].isin([alt_mode, Mode.CAR])], 
        x=column, 
        color="mode", 
        barmode="overlay",
        color_discrete_sequence=["orange", "blue"],
        histnorm="probability density"
    )
    
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
    
    # make space for explanation / annotation
    # fig.update_layout(margin=dict(b=100))

    # add annotation
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

