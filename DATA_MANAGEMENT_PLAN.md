# Data Management Plan

This data outlines the standards by which we will manage data and code for Metropolitan Council's VMT Reduction Mode Shift Study.  The central purpose of this study is to analyze the mode shift potential of 500,000+ real-world trips reported by residents in the 2019 and 2021 Travel Behavior Inventory surveys for which detailed origin and destination coordinates are available.  It is to rely on open-source tools such that 1) Council staff can repeat this analysis for future waves of the TBI, and 2) others outside the Council can apply the tools to their own data sets.   

## Protected and Public Data

This project combines several main types of data: 

- The Travel Behavior Inventory (TBI) data come from multiple waves of a smartphone enabled household travel survey. These data include detailed attributes about sampled households and people, coordinates and timestamps of their phone's movements, and reported details about trip purpose, mode, etc.  These data include personally identifiable information (PII) and care should be taken to protect the privacy of the respondents and the data should be considered confidential.  Therefore, only aggregate summaries that would not reveal PII should be shared publicly.
  
- OpenStreetMap (OSM) network data.  OSM includes attributes of the transportation network, including types of roads, walk paths, bike paths, and points of interest.  These data are available publicly and there is no restriction on sharing them. 

- General Transit Feed Specification (GTFS).  GTFS data show transit network and schedule, as provided by Metro Transit.  These data are available publicly and there is no restriction on sharing them. 

- StreetLight Data speeds and volumes.  Speed and volume information is collected from the SteetLight Data API.  Auto travel speeds are attached to the OSM network to allow the paths to be built on congested times.  These data are from a commercial source, and their use is dictated by the Council's agreement with the vendor.  It is fine to share derivative products including aggregated data (average weekday speed by hour), but not the records queried from their API.
  
- Disaggregate output data.  The main outputs of this study include routes by mode, and the feasibility and likelihood of shifting modes for individual trips and tours found in the TBI.  Any disaggregate data that risks revealing PII should be considered confidential and protected accordingly.  

- Aggregate output data.  Summaries of the analysis, including maps, table, figures, etc. that do not reveal PII are safe to share publicly.

- Code, scripts and documentation.  All code, scripts and associated documentation will be open-source and published on the project's Github repository.  

Unless there is a specific concern with respect to revealing personally identifiable information or violating a commercial data use agreement, all data, code and documentation associated with this project will be publicly available, as outlined in this data management plan, to allow the work to be replicated and repeated elsewhere.  This includes all deliverables, along with such working papers, calculations, notes, and other information used to produce the deliverables.

## Code and Document Management

The code, as well as associated documentation and reports, used in this study will be checked-into the project's Github repository.  When working on an intermediate step, users should create a new branch.  When that intermediate step is complete, the user will create a pull request into the main branch, and request review from Council staff.  Upon successful review, and after any necessary changes, that branch will be merged into the main branch.  

The repository should not be used to store data.  Instead, data should be shared on the shared network drive--the Microsoft Teams folder hosted by the University of Kentucky.  This prevents large files from overwhelming the changes in git.  

Care should be taken to avoid committing any PII to the repository.  This includes any exploratory results that may be reported in a Jupyter notebook.  To accomplish this, the .gitignore file should ensure that .csv or other data file formats are specifically ignored by git.  In addition, users should clear any notebook cells before checking them in.  

Project documentation and reports will generally be written in markdown or equivalent such that the version can be tracked.  

The code and documents stored on the Council's Github site will be considered a deliverable that is property of the council.  That code may reference other third-party software, including software developed by members of the project team, such as TransitRouter.js.  Such third-party software will still be owned by its original developer, even if it is used in this project, or enhanced as part of this project.  In general, the delineation of ownership will be determined by the owner of the Github repository where it lives.   

## Data Retention and Availability

The main project repository is currently private to minimize the risk of inadvertently pushing PII, but will be made public at the end of the project.  The repository will be retained indefinitely at that location to allow others to use it.  Those wishing to access other data should contact Council staff.  

## Publishing

The results of this study will be presented to Council staff and the Council Board.  They may also be of interest to the community more broadly, including people in other regions who may wish to apply the method locally, or learn from the Council's experience.  Therefore, members of the project team are encourage to publish these findings and derivative analyses in academic journals, industry newsletters, or other venues, to present the findings at professional conferences and seminars.  