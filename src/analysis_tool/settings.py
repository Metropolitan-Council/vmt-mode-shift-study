import yaml
import streamlit as st
import geopandas as gpd
import pyproj

# conda's proj activation sets PROJ_NETWORK=ON; failed grid downloads make to_crs return inf
pyproj.network.set_network_enabled(False)

# read in the config yaml and turn (all of) it into a dictionary that can be queried from
with open("config.yaml", "r", encoding="utf-8") as stream:
    try:
        handler = yaml.safe_load(stream)
        scenario = handler['scenarios'][handler['scenario_to_run']]
    except yaml.YAMLError as exc:
        raise RuntimeError("Error parsing the yaml file")

# get the communities df (cached for future use since it does not change)
@st.cache_data()
def get_communities() -> gpd.GeoDataFrame:
    """
    This function returns a formatted/simplified communities GeoDataFrame in EPSG:4326 and indexed by CTU name. The results are cached, as all requests
    should be the same.

    Returns:
        gpd.GeoDataFrame: A GeoDataFrame of CTUs in EPSG:4326 indexed by CTU_NAME strings
    """
    communities = gpd.read_file(f"data/{handler['community_shape_file_name']}")
    # source is UTM 15N (EPSG:26915); simplify in meters there, avoiding estimate_utm_crs DB lookup
    communities = communities.to_crs("EPSG:26915")
    communities["geometry"] = communities.simplify(50)
    return communities.to_crs("EPSG:4326").set_index("CTU_NAME")
