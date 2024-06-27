These scripts are used in preparing the TBI data:

1. `Clean and Decode TBI.ipynb` Run this script first to process the raw TBI data.  This merges the data across waves, defines consistent field names, aggregates trip purposes and modes and filters out potentially problematic records.  The output is written to `tbi_cleaned.csv` on the shared folder.  Minor changes may be needed for future TBI waves if the data format changes.  

2. `OSM_Speed_Volume_via_Streetlight_API.ipynb` We start from an extraction from OpenStreetMap (OSM) as a representation of the road network.  This script uses the StreetLight API to find the congested speeds and attach them to the OSM network.  

3. `rerouting_validation.ipynb` This is optional, but runs some checks to see if the attached routes are logical.  Before checking the re-routing, you need to run the routing steps in the main /src folder.  

