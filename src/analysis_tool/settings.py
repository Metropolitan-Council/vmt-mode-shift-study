import yaml
import streamlit as st
import geopandas as gpd
import pandas as pd

# read in the config yaml and turn (all of) it into a dictionary that can be queried from
with open("config.yaml", "r", encoding="utf-8") as stream:
    try:
        handler = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        raise RuntimeError("Error parsing the yaml file")
    
@st.cache_data()
def get_data() -> pd.DataFrame():
    if handler["tbi_file_name"].split(".")[-1] == "parquet":
        df = pd.read_parquet("data/" + handler["tbi_file_name"])
    elif handler["tbi_file_name"].split(".")[-1] == "csv":
        df = pd.read_csv("data/" + handler["tbi_file_name"])
    else:
        raise RuntimeError()
    
    return df

# get the communities df (cached for future use since it does not change)
@st.cache_data()
def get_communities() -> gpd.GeoDataFrame:
    """
    This function returns a formatted/simplified communities GeoDataFrame in EPSG:4326 and indexed by CTU name. The results are cached, as all requests
    should be the same.

    Returns:
        gpd.GeoDataFrame: A GeoDataFrame of CTUs in EPSG:4326 indexed by CTU_NAME strings
    """
    communities = gpd.read_file(f"data/{handler['community_shape_file_name']}").to_crs("EPSG:4326")
    communities["geometry"] = (
        communities.to_crs(communities.estimate_utm_crs()).simplify(50).to_crs(communities.crs)
    )
    return communities.set_index("CTU_NAME")
