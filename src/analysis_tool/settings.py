import yaml
import streamlit as st
import geopandas as gpd

with open("config.yaml", "r") as stream:
    try:
        handler = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        handler = None
        print(exc)
    
@st.cache(allow_output_mutation=True)
def get_communities():
    communities = gpd.read_file(f"data/{handler.get_community_path()}").to_crs("EPSG:4326")
    communities["geometry"] = (
        communities.to_crs(communities.estimate_utm_crs()).simplify(50).to_crs(communities.crs)
    )
    return communities
