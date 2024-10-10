This folder contains the route visualizer.  There are two scripts that prep the data:

If you have access to the network drive, you do not need to re-run these scripts. Read the appropriate parquet files from our network drive. 

1. convert\_tbi\_locations\_to\_gdf - Converts the CSV file of TBI GPS traces to a faster format, and converts other route files to parquet files, which are much faster to read than gpkg files.  

2. select\_congested\_car\_data - When creating the car routes, we create routes for all times of day reflecting different congestion levels.  This script selects the appropriate times of day and writes them all to one file.  There is a variation on this to select the values for the car scenario. 

The main script is vmt\_viz\_routes\_2.  Instructions are in the notebook.  

