import pandas as pd
import geopandas as gpd
import geoplot as gplt

from matplotlib.colors import LinearSegmentedColormap

rg = LinearSegmentedColormap.from_list('rg',["r", "w", "g"], N=256) 
rg.set_bad(color="grey")

communities = gpd.read_file("../data/shp_society_thrive_msp2040_com_des").to_crs("EPSG:4326")

class BaseStep:
    
    def __init__(self, df: pd.DataFrame, name: str, mode: str):
        self.df = df
        self.name = name
        self.mode = mode
        
    def get_summary_statistics(self):
        raise NotImplementedError("Please implement this function")
    
    def get_summary_figure(self):
        raise NotImplementedError("Please implement this function")
    
    def apply_step(self, expression: pd.Series, prev: pd.Series):
        self.df[f"feasible_{self.mode}_shift"] = prev
        
        self.df[self.name] = True
        self.df.loc[expression][self.name] = False
        self.df.loc[expression][f"feasible_{self.mode}_shift"] = False
    
    def get_statistics(self, prev: pd.Series):
        percent_shifts_before = len(self.df[(self.df['self.mode']=='Car') & (prev)]) / len(self.df[self.df['self.mode']=='Car']) * 100
        percent_shifts_after = len(self.df[(self.df['self.mode']=='Car') & (self.df[f'feasible_{self.mode}_shift'])]) / len(self.df[self.df['self.mode']=='Car']) * 100
        
        prev_vmt = self.df[(self.df["self.mode"] == "Car") & (prev)]["vmt"].sum()
        after_vmt = self.df[(self.df["self.mode"] == "Car") & self.df[f"feasible_{self.mode}_shift"]]["vmt"].sum()
        
        return ((percent_shifts_before, percent_shifts_after), (prev_vmt, after_vmt))
    
    def get_map(self):
        communities["val"] = (self.df.groupby("community")[self.name].sum() / self.df.groupby("community")[self.name].count()).fillna(0)
        return gplt.choropleth(communities, hue=communities["val"], projection=gplt.crs.AlbersEqualArea(), cmap=rg, figsize=(12, 12))


class ContinuousStep(BaseStep):
    
    def __init__(self, df: pd.DataFrame, name: str, mode: str, cutoff: float):
        super().__init__(df, name, mode)
        self.cutoff = cutoff
        
    def get_summary_statistics(self):
        return super().get_summary_statistics()
    
    def get_summary_figure(self):
        return super().get_summary_figure()
    
    def apply_step(self, expression: pd.Series, prev: pd.Series):
        super().apply_step(expression, prev)
    
    def get_statistics(self, prev: pd.Series):
        return super().get_statistics(prev)
        
    def set_cutoff(self, new_cutoff: float):
        self.cutoff = new_cutoff
        
    def get_map(self):
        return super().get_map()
    

class CategoricalStep(BaseStep):
    
    def __init__(self, df: pd.DataFrame, name: str, mode: str):
        super().__init__(df, name, mode)
        
    def get_summary_statistics(self):
        return super().get_summary_statistics()
    
    def get_summary_figure(self):
        return super().get_summary_figure()
    
    def apply_step(self, df: pd.DataFrame):
        super().apply_step()
    
    def get_statistics(self, mode: str, df: pd.DataFrame, prev: pd.Series):
        return super().get_statistics(mode, df, prev)