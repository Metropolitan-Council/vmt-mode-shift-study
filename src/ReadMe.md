This is the main set of tools produced by this project.  There are two tools:

1. `routing` This produces alternative routes for each TBI trip.  Run this first.  The routes will be written as .parquet files in the shared folder. 

2. `analysis_tool` This does the analysis comparing the non-car options to all observed car trips.  It is an interactive tool and requires both the processed TBI data and the routes. 

Instructions for running each are in the relevant folder. 