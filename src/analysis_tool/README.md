# VMT Mode Shift Analysis Tool

## Setup

To get this tool up and running on your machine, there are three main options:

1. Full local installation

To run this tool locally, setup the python environment locally using either condaforge/mambaforge and the top-level environement.yml file, set the main data directory in keyring, cd to this directory (src/analysis_tool), and then run ```streamlit run main.py``` in the command line. The application will then appear in your local web browser. 

The top-level environment.yml is geared towards windows and may fail for linux/mac machines. In the case that installation fails with environment.yml, a more general and platform-agnostic environemnt can be found in simple_environment.yml, which contains the base packages needed to run the tool (conda/mambaforge should be able to fill in the blanks). 

2. Docker

Alternatively, to skip enivornment setup, this tool can be ran/hosted (on an internal network) using docker. First, [download docker](https://www.docker.com/) onto your local machine and open the docker daemon (program). Afterwards, in your command line interface, run ```docker pull yianzhang14/streamlit```. With that done, you can then run ```docker run -it --rm -p 8501:8501 streamlit```, and the streamlit app will automatically boot up within the docker virtual container. With this done, you can go to ```localhost:8501``` on your browser to access the application. It should be noted that while the setup here is much simpler and consistent than in method 1, the docker container will likely be more memory-hungry due to the overhead of running the underlying container. 

3. Public website endpoint

To avoid any local installation entirely, the streamlit app can also be [found online](https://vmt-visualization-demo-5qbtm4cfi09.streamlit.app/), with the streamlit community cloud providing the hosting for the website. During times of higher traffic (whether it is traffic to the tool or to streamlit in general during peak hours), this website may be somewhat slow due to limited resources.

## Data pipeline

The main raw inputs for this vmt mode shift analysis tool are listed below:

1. TBI community survey data 
2. Rerouting files
3. Various sources of external data (weather data, community shapefiles, etc.)

The former two data inputs are located on the main VMT Reduction Mode Shift OneDrive, and the latter is collected in the tbi_full.csv file as well as other assorted csv/shape files in the data/ directory.

With the second input being generated and the third input being largely single-focused, the first input is the one that has gone through the most cleaning and processing. The files that are responsible for this can be found in the data_processing/ directory and, in particular, the ```Clean and Decode TBI.ipynb``` notebook. This step merges the two raw TBI inputs (one for each wave of the survey), drops non-useful columns, cleans up some names/values, and does some overall cleaning/merging (in particular converting unlinked trips to grouped linked trips). There are also some basic sanity check conditions in place at the end of the notebook that takes out nonsensical trips from the dataset. The cleaned file can also be found on the OneDrive under the name ```tbi_cleaned.csv```.

More information about specifics of the cleaning such as the % of rows that remain after cleaning can be found in the notebook, and more information about the schema for the TBI data that motivates the cleaning can be found on the OneDrive alongside the raw TBI data.

Some initial visualizations and explorations of this cleaned TBI file, especially with respect to the feasibility/probable analysis of this project, can be found in the reports/exploratory_data_analysis directory. These are essentially a precursor to this fully-fledged, interactive tool.

In this tool, some further processing of the cleaned tbi file is done, which is coded in the ```initialize.py``` python script. This mainly involves merging in the rerouting files to get durations/distances of alternative modes as well as some basic manipulation of columns to mesh in with the expectations of the tool. This only needs to be done once--the results of this processing is saved to the data/ directory. It should be noted that this initial processing may take a while; the process of downloading the data inputs from the OneDrive can take a bit if your Wi-fi is not very fast. 

There is also another notebook (```anonymize.ipynb```) that turns this fully processed file into a compressed and anonymized parquet file. Latitudes and longitudes are removed, values are rounded, ids are standardized, and datatypes are explicitly specified.

## Using the tool

The most essential component to this tool is streamlit, a python package that can be used to create visualization websites easily. This package provides many widget functionalities to alter the layout/content of the website, and the general gist of it is that it runs through the entirety of the code every time something changes on its website, with control flow and session state variables serving as ways to guide that running. 

The main logic of this app can be found in the ```main.py``` file, which is the main handler of the streamlit app. It creates essentially all the displayed text/images on the website, handles the pages of the streamlit app, and keeps track/updates session state variables. However, the core of the feasibility and probability analysis of VMT mode shift is found in the steps/ directory. Here, various steps that should be run in the tool can be defined, all inheriting from a generalized parent step. These specialized steps specify the basic information about a step, the figures that should be displayed along with that information, and how the step should actually be applied.

There are also some settings relating to the app that can be changed in the ```config.yaml``` file. These include details such as paths towards necessary datafiles, the columns to keep from the csv file, various parameters the tool uses for some steps, and whether or not to force rebuilding the data (which is useful in the case of accidental alterations to the input file). In general, the default values should be fine though, and not much needs to be changed for the tool to work.