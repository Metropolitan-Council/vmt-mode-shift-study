# How To

From top to bottom, here is how to run the project materials. 

Assumptions:
- You have Python 3 and conda installed on your machine.
- You have access to the Teams/Sharepoint location for the project materials.
- You are working in VS Code
- You are working on a Mac

## Setup

- Set up the development environment with conda as shown in the [README](README.md)
- Establish the Teams/Sharepoint location 
- If you are re-running the project, you may want to copy the existing data to another location

```python
# User set the main directory using keyring.  For example:
   import keyring
   keyring.set_password('msp', 'vmt_reduction_dir', 'path to the desired directory')
# This will be saved on your local machine
```

## What are you trying to do?

- Re-run feasibility and probability analyses on project data (no new network, TBI, or other data)? -> go to ## Final reporting notebooks
- Build new networks, update routing data? -> go to ## Start running things


## Final reporting notebooks

These take in the cleaned TBI, networks, various routed trips, and produce the potential trips shifted between modes.

- reports/exploratory_data_analysis/feasibility_analysis_cleaned.ipynb
- reports/exploratory_data_analysis/probable_analysis_cleaned.ipynb

The project left us with networks and routed trips. These live in Data_Processed/geodata.

## Start running things

1. Prepare data. Run the following python notebooks. For each, open and select the `vmtmodeenv` environment as the kernel.
    - The project left us with analysis_area.osm.pbf (OpenStreetMap extract for the analysis area)
    - Clean and Decode TBI.ipynb [](data_processing/Clean%20and%20Decode%20TBI.ipynb) -> new final output in `data_processing/cleaned_decoded_tbi.csv`
    - [optional, only rerun if we want new StreetLight data, like if we are going to use a new starting network] OSM_Speed_Volume_via_StreetLight_API.ipynb [](data_processing/OSM_Speed_Volume_via_StreetLight_API.ipynb) -> produces teams_dir + '/2-Re-Routing Analysis/OSM/output'. This is a record of how the StreetLight data was obtained and will require updates depending on StreetLight Data offerings, API changes, and access.
    - Convert TBI locations to gdf/geoparquet [](data_viz/convert_tbi_locations_to_gdf.ipynb)

2. Review exploratory data analysis. Make sure nothing is broken.
    - Examine Departure Arrival and Duration.ipynb [](reports/exploratory_data_analysis/Examine%20Departure%20Arrival%20and%20Duration.ipynb)
    - exploratory_data_analysis.ipynb [](reports/exploratory_data_analysis/exploratory_data_analysis.ipynb)
    - exploratory_data_analysis_summary.ipynb [](reports/exploratory_data_analysis/exploratory_data_analysis_summary.ipynb)

2. Prepare for and perform routing -> see [src/routing/README.md](src/routing/README.md)

    - Run reports/exploratory_data_analysis/geodata.ipynb [](reports/exploratory_data_analysis/geodata.ipynb) to create parquet files for routed trips
    - [optional, rerun AFTER running src/] rerouting_validation.ipynb [](data_processing/rerouting_validation.ipynb)
    - Run routing

# Updating options

- Add 2023 TBI data and re-run all subsequent data processing, routing, and analysis steps? Maybe, but networks and routes available will have changed. 
- Update community designations to 2050 (area_for_way.jl)




Routing QC report inputs: input_files.yml maps the reports to these routed files under Data_Processed/geodata:

Car: baseline car_congestion_1d39c/car_congestion.parquet; scenario car_scenario_f2802.parquet
Walk: baseline walk-trips-1d39c.parquet; scenario walk-scenario-a37e1.parquet
Bike: baseline bike-lts-37721.parquet; all-LTS-1 bike-all-lts1-37721.parquet; e-bike bike-ebike-8a1a0.parquet
Transit: baseline transit-trips-45d51.parquet; scenario transit-scenario-0277d.parquet
The QC book includes calibration, walk scenario, bike scenario, transit baseline, transit scenario, and car scenario reports, as listed in _quarto.yml. The scenario checks compare the corresponding baseline and scenario files.

Analysis app scenarios: config.yaml defines base, best_walk, best_bike, e_bike, double_transit, slow_car, old_slow_car, and all_four. Its scenario_to_run is currently base, so that is the selected app scenario—not all eight.

There are version mismatches worth noting: the app config points several scenarios to transit baseline transit-trips-7d58f.parquet, while QC maps baseline to transit-trips-45d51.parquet; the app’s e-bike route has a -1 suffix, but the QC mapping does not. The QC mapping is the clearest record of which files those final routing checks consume
