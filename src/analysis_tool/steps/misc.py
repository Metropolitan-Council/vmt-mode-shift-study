import pandas as pd

def get_step_statistics(mode: str, df: pd.DataFrame, prev: pd.Series):
    percent_shifts_before = len(df[(df['mode']=='Car') & (prev)]) / len(df[df['mode']=='Car']) * 100
    percent_shifts_after = len(df[(df['mode']=='Car') & (df[f'feasible_{mode}_shift'])]) / len(df[df['mode']=='Car']) * 100
    
    prev_vmt = df[(df["mode"] == "Car") & (prev)]["vmt"].sum()
    after_vmt = df[(df["mode"] == "Car") & df[f"feasible_{mode}_shift"]]["vmt"].sum()
    
    return ((percent_shifts_before, percent_shifts_after), (prev_vmt, after_vmt))