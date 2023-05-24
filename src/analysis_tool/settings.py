import yaml
import streamlit as st
import geopandas as gpd

with open("config.yaml", "r", encoding="utf-8") as stream:
    try:
        handler = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        raise RuntimeError("Error parsing the yaml file")
    
@st.cache(allow_output_mutation=True)
def get_communities():
    communities = gpd.read_file(f"data/{handler['community_shape_file_name']}").to_crs("NAD83")
    communities["geometry"] = (
        communities.to_crs(communities.estimate_utm_crs()).simplify(50).to_crs(communities.crs)
    )
    return communities
