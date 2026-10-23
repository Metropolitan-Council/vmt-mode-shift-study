# How To

From top to bottom, here is how to run the project materials. 

Assumptions:

- You have Python 3, conda, R, and Quarto installed on your machine.
- You have access to the Teams/Sharepoint location for the project materials.
- You are working in VS Code or another IDE that supports quarto, python, Jupyter notebooks, and streamlit apps. 
- You are working on a Mac. If on Windows, you will have to adapt the code.

## Setup

- Set up the development environment with conda as shown in the [README](README.md)
- Establish the Teams/Sharepoint location with keyring as shown below
- If you are re-running the project, you may want to copy the existing data to another location so that you have a backup of the original files.

```python
# User set the main directory using keyring.  For example:
   import keyring
   keyring.set_password('msp', 'vmt_reduction_dir', 'path to the desired directory')
# This will be saved on your local machine
```

## What are you trying to do?

- Re-run feasibility and probability analyses on project data (no new network, TBI, or other data)? -> go to "Final reporting analysis" section.
- Add new TBI data, build new networks, finesse assumptions, update routing? -> go to "Running from scratch" section.

## Final reporting analysis

These take in the cleaned TBI, networks, various routed trips, and produce the potential trips shifted between modes.

The project left us with networks and routed trips. These live in the SharePoint under Data_Processed/geodata. [src/analysis_tool/CHANGELOG.md](src/analysis_tool/CHANGELOG.md) contains a record of the exact route files used in the final analyses. 

### Notebooks

The notebooks walk through the logic of analyzing the feasibility and probability of trips being shifted between modes. They ultimately aren't used for generating final reports, but rather for understanding and validating the analysis process.

- reports/exploratory_data_analysis/feasibility_analysis_cleaned.ipynb
- reports/exploratory_data_analysis/probable_analysis_cleaned.ipynb

### Streamlit App

The streamlit app (src/analysis_tool) allows you to set different cutoff values for determining the feasibility and probability of trips being shifted between modes. You can also run with default values without making any changes. The app also allows you to export the results of the analyses in src/analysis_tool/output.

The app also allows the user to subset the data by city, based on the start and end locations of the individual trips.

See [src/analysis_tool/](src/analysis_tool/README.md)

### Summary report

The summary report consolidates the findings from the feasibility and probability analyses and uses saved outputs from the streamlit app to generate a report following the same structure as [VMT Reduction Mode Shift Final Report.pdf](VMT Reduction Mode Shift Final Report.pdf). 

See [reports/summary_report/README.md](reports/summary_report/README.md) for more details. 

Note that for the final report, the definition of a probable trip is simplified to a trip that is within 15 minutes of the travel time by car. 

## Running from scratch

Set up the Python environment by creating and activating the `vmtmodeenv` environment.

1. Prepare data. Run the following python notebooks. For each, open and select the `vmtmodeenv` environment as the kernel.
    - The project left us with analysis_area.osm.pbf (OpenStreetMap extract for the analysis area)
    - Clean and Decode TBI.ipynb [](data_processing/Clean%20and%20Decode%20TBI.ipynb) -> new final output in `data_processing/cleaned_decoded_tbi.csv`
    - [optional, only rerun if we want new StreetLight data, like if we are going to use a new starting network] OSM_Speed_Volume_via_StreetLight_API.ipynb [](data_processing/OSM_Speed_Volume_via_StreetLight_API.ipynb) -> produces teams_dir + '/2-Re-Routing Analysis/OSM/output'. This is a record of how the StreetLight data was obtained and will require updates depending on StreetLight Data offerings, API changes, and access.
    - Convert TBI locations to gdf/geoparquet [](data_viz/convert_tbi_locations_to_gdf.ipynb)

1. Review exploratory data analysis. Again, select the `vmtmodeenv` environment as the kernel for each notebook.
    - Examine Departure Arrival and Duration.ipynb [](reports/exploratory_data_analysis/Examine%20Departure%20Arrival%20and%20Duration.ipynb)
    - exploratory_data_analysis.ipynb [](reports/exploratory_data_analysis/exploratory_data_analysis.ipynb)
    - exploratory_data_analysis_summary.ipynb [](reports/exploratory_data_analysis/exploratory_data_analysis_summary.ipynb)

1. Prepare for and perform routing -> see [src/routing/README.md](src/routing/README.md)
1. Run analysis tool -> see [src/analysis_tool/ReadMe.md](src/analysis_tool/ReadMe.md)
1. Run summary report -> see [reports/summary_report/README.md](reports/summary_report/README.md)

# Future updates

Updating to more recent TBI data requires not only obtaining the new TBI datasets, but also ensuring that all dependent data processing, routing, and analysis steps are updated accordingly.  

Data needed to update the analysis

- 2023 TBI and future TBI data
    - Review assumptions about 95 percentile cutoff values
    - Verify consistency with previous TBI datasets (2019, 2021)
- Community designations to 2050 (area_for_way.jl)
- COCTU boundaries
- GTFS schedules for Metro Transit and other regional transit agencies
- Speed limits and free-flow speeds
- Bike and ped LTS data 
- Weather data
- TAZ terminal times
- OSM Network

Other considerations
- Construction schedules and effects on travel times and route availability in newer years
- Any updates on NACTO guidelines for speed, or other industry reccomendations
