## Exploratory Data Analysis & Feasibility Analysis

This folder contains the scripts used to create three reports:

1. Exploratory Data Analysis: The summary report is `exploratory_data_analysis.html`.  It documents the basics of what are in the TBI data. 

2. Feasibility Analysis: Summary report is `feasibility_analysis_cleaned.hmtl`.  This report examines which trips could feasibly switch to another mode, given a set of rule-based constraints.  In general, the constraints are set such that 95% of trips on the mode we wish to switch to remain feasible.  For example, we observe that 95% of walk trips are shorter than 1.6 miles, so only car trips shorter than 1.6 miles can feasibly switch to walk.
   
3. Likelihood Analysis: Summary report is `probable_analysis_cleaned.html`.  Here we consider which trips are likely to switch to a non-car mode.  To switch, these trips must first be feasible, so the likely trips are a subset of the feasible trips.  Here, our basic rule is that trips are likely to switch to a mode if the best 50% of observed trips on that mode meet the condition.  For example, 50% of existing walk trips are less than 0.4 miles (about an 8 minute walk), so we consider car trips shorter than 0.4 miles as likely to switch.  The reasoning is that people who do not yet walk are probably less inclined to walk than those who walk already, so we should focus on shifting those trips with the best alternatives. 

There are several supporting files and steps used to create these reports.  The final step of each is a Jupyter notebook of the same name.  The notebook is compiled to an HTML file using [Quarto](https://quarto.org/) and the command: 

	quarto render file_name.ipynb --to html 

Alternatively, it can be rendered to a PDF or Microsoft Word Document.  In this way, the charts and tables can be easily changed if the data or analysis changes, but the code is hidden from the end user.  

The steps before this include:

- `explore_route_data.ipynb` - A basic analysis of the routes.  We can delete this file in clean up when the project is finished. 
- `exploratory_data_analysis.ipynb` - This can be run stand-alone. 
- `geodata.ipynb` - Script to pre-process route data into faster to read files. 
- `feasibility_analysis.ipynb` - Our initial development script.  Contains some further data exploration, but can probably be deleted when the project is complete. 
- `feasibility_analysis_cleaned.ipynb` - The main feasibility analysis. 
- `probable_analysis_cleaned.ipynb` - The main likelihood analysis. To be run after the feasibility analysis. 

