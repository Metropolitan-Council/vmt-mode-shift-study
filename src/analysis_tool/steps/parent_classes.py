import pandas as pd
import geopandas as gpd
import geoplot as gplt

from matplotlib.colors import LinearSegmentedColormap

rg = LinearSegmentedColormap.from_list('rg',["r", "w", "g"], N=256) 
rg.set_bad(color="grey")

from . mode_enum import Mode

communities = gpd.read_file(r"C:\Work\research\vmt-mode-shift-study\src\analysis_tool\data\shp_society_thrive_msp2040_com_des").to_crs("EPSG:4326")
    
class BaseStep:
    
    def __init__(self, df: pd.DataFrame, name: str, mode: Mode):
        self.df = df
        self.name = name
        self.mode = mode
        self.prev = pd.to_numeric(self.df[f"feasible_{mode}_shift"]).copy()
        
    def get_summary_statistics(self):
        raise NotImplementedError("Please implement this function")
    
    def get_summary_figure(self):
        raise NotImplementedError("Please implement this function")
    
    def apply_step(self, expression: pd.Series) -> None:
        self.df.loc[:, f"feasible_{self.mode}_shift"] = self.prev
        
        self.df.loc[:, self.name] = True
        self.df.loc[expression, self.name] = False
        self.df.loc[expression, f"feasible_{self.mode}_shift"] = False
    
    def get_step_statistics(self):
        percent_shifts_before = len(self.df[(self.df['mode']==Mode.CAR) & (self.prev)]) / len(self.df[self.df['mode']==Mode.CAR]) * 100
        percent_shifts_after = len(self.df[(self.df['mode']==Mode.CAR) & (self.df[f'feasible_{self.mode}_shift'])]) / len(self.df[self.df['mode']==Mode.CAR]) * 100
        
        prev_vmt = self.df[(self.df["mode"] == Mode.CAR) & (self.prev)]["vmt"].sum()
        after_vmt = self.df[(self.df["mode"] == Mode.CAR) & self.df[f"feasible_{self.mode}_shift"]]["vmt"].sum()
        
        return ((percent_shifts_before, percent_shifts_after), (prev_vmt, after_vmt))
    
    def get_map(self):
        temp = self.df[self.df["community"] != -1][["community", self.name]]
        
        values = (temp.groupby("community")[self.name].mean()).fillna(0)
        communities["val"] = values
        return gplt.choropleth(communities, hue=communities["val"], projection=gplt.crs.AlbersEqualArea(), cmap=rg, figsize=(12, 12))
    
    def __repr__(self) -> str:
        return "Running the step with " + self.name + " as a criteria for shifts to " + self.mode


class ContinuousStep(BaseStep):
    
    def __init__(self, df: pd.DataFrame, name: str, mode: Mode, cutoff: float):
        super().__init__(df, name, mode)
        self.cutoff = cutoff
        
    def set_cutoff(self, new_cutoff: float) -> None:
        self.cutoff = new_cutoff
    

class CategoricalStep(BaseStep):
    pass