import pandas as pd
import matplotlib.pyplot as plt

from steps.parent_classes import ContinuousStep
from steps.enums import *
from steps.figure_lib import *

import inspect

class BikeSnowDepthStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "feasible_bike_snow_depth", Mode.BIKE, cutoff, "snow_depth", Phase.FEASIBLE)
    
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in Mode.get_all()], percentile=self.get_cutoff_pct())
    
    def get_summary_figure(self):
        fig = plot_density_plotly(self.df, self.mode, self.column_name, self.get_cutoff_pct())
        fig.update_layout(
            title={
                'text': "Snow depth during travel day for all modes",
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            xaxis_title="Probability Density",
            yaxis_title="Snow Depth (mm)",
            legend_title="Legend"
        )
        return fig
    
    def apply_step(self):
        if self.cutoff_mode == CutoffMode.PCT:
            super().apply_step(self.df[self.column_name] > self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
        elif self.cutoff_mode == CutoffMode.RAW:
            super().apply_step(self.df[self.column_name] > self.cutoff)
        else:
            raise RuntimeError("Something went wrong with the cutoff mode enum")
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""Snowing can impact the feasibility for various modes significant, but this effect is particularly pronounced for biking. This is due to the snow decreasing the traction a bike can get to manuever and due to the discomfort that would arise from traveling through freezing temperatures at fast speeds, exposed fully to the elements. 

        Snow depth is measured in mm and is defined by NOAA (https://www.weather.gov/gsp/snow) as the total depth of snow, ice pellets, or ice on the ground at the time of observation, gauged using a measuring stick. This figure is meant to represent the average depth of snow/ice at ground level at the usual measurement site. (snowfall is measured using a snowboard w.r.t. the previous observation--is accumulation of snow over a day).""")
        
        # summary figure
        res.append("""Below is a comparison of snow depth distributions between all the different modes. It is clear here that bike/scooter is an outlier, with the specified percentile much more to the left than the other mode percentiles. This indicates that snow depth is a strong and unique indicator for determining whether a bike trip is feasible. """)
        
        # summary statistics
        res.append("Below, the summary statistics for the snow depth (in mm) for observed bike/scooter trips can be seen. It should be noted that at the default 95th percentile parameter, the snow depth for these trips remain at 0. ")
        
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res
    
    
class BikeHighLTSDistStep(ContinuousStep):
    
    def __init__(self, df: pd.DataFrame, cutoff=0.95):
        super().__init__(df, "feasible_bike_high_lts_dist", Mode.BIKE, cutoff, "high_lts_biking_pct", Phase.FEASIBLE)
        
        df.loc[:, "high_lts_dist"] = df["bike_distance_meters_3"] + df["bike_distance_meters_4"]
        df.loc[:, "high_lts_biking_pct"] = df["high_lts_dist"] / df["bike_distance_meters"]
        
    def get_summary_statistics(self):
        return show_summaries(self.df, modes=[[x, self.column_name] for x in [self.mode, Mode.CAR]], percentile=self.get_cutoff_pct())
    
    def get_summary_figure(self):
        fig = plot_density_plotly(self.df, self.mode, self.column_name, self.get_cutoff_pct())
        fig.update_layout(
            title={
                'text': r"% of bike trip on high LTS routes for observed bike and car trips",
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            xaxis_title="Probability Density",
            yaxis_title="% High LTS",
            legend_title="Legend"
        )
        return fig
    
    def apply_step(self):
        if self.cutoff_mode == CutoffMode.PCT:
            super().apply_step(self.df[self.column_name] > self.df[self.df["mode"] == self.mode][self.column_name].quantile(self.cutoff))
        elif self.cutoff_mode == CutoffMode.RAW:
            super().apply_step(self.df[self.column_name] > self.cutoff)
        else:
            raise RuntimeError("Something went wrong with the cutoff mode enum")
        
    def get_text(self) -> list[str]:
        conclusion = super().get_text()
        res = []
        # intro
        res.append("""The level of traffic stress (lts) quantifies how stressful/difficult it is to bike in a location, ranging from places with dedicated bike lanes at lts 1 to main streets without any developed biking infrastructure at lts 4. LTS 1 streets are considered safe and comfortable by almost all riders, LTS 2 for most adults, whereas LTS 3 and 4 are more stressful.

        The distance through high traffic stress locations an individual would have to bike through to reach a destination is thus likely strong indicator for the feasibility that a trip could switch to biking. Here, we consider the percent distance traveled during a trip on the higher lts categories, 3 and 4. 

        We consider the percentage in particular because car trips are naturally longer than biking trips and distances are already accounted for, so percentages even things out for consideration. """)
        
        # summary figure
        res.append("""It is very clear here from this figure that observed bike trips tend to be far more left-heavy for high stress distance than car trips (if they were to switch to biking), which makes sense as the reason these bike trips are observed is because they are feasible. The lines represent the specified percentiles for each of the two distributions, and any part of the orange distribution to the left of the blue line can feasibly switch to biking, under the high stress biking distance feasibility indicator. """)
        
        # summary statistics
        res.append("Here, we can see the summary statistics for high stress biking distance between observed biking/observed car trips, if the latter were to switch to biking. This largely reflects what was seen in the distribution comparison figure. ")
        
        res = res + conclusion
        res = [inspect.cleandoc(x) for x in res]
        
        return res