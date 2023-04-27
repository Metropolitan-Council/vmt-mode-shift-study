This folder contains the route visualizer.  There are two scripts that prep the data:

1. convert_tbi_locations_to_gdf - Converts the CSV file of TBI GPS traces to a faster format, and converts other route files to parquet files, which are much faster to read than gpkg files.  
2. select_congested_car_data - When creating the car routes, we create routes for all times of day reflecting different congestion levels.  This script selects the appropriate times of day and writes them all to one file.  

These only need to be run if the input files change.  Otherwise, just read the appropriate parquet files from our network drive. 

The main script is vmt_viz_routes_2.  Instructions are in the notebook.  