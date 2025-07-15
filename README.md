
# VMT Reduction and Maximum Mode Shift Study

This study estimates the maximum amount of mode shift possible given existing transportation infrastructure, land use, and travel patterns. Unlike travel forecasting models, this project does not model changes to the transportation system, population size, or where people live, work, shop, and travel. By analyzing the current system, the project estimates the baseline potential for behavioral changes alone to reduce vehicle miles traveled and increase the share of trips made by walking, transit, or biking.

Further details and study conclusions available on [metrocouncil.org](https://metrocouncil.org/Transportation/Performance/Travel-Behavior-Inventory/Data/Maximum-Mode-Shift.aspx).

Presentations and reports

| Item     | Link |
| -------- | ------- |
| Final PDF report | [link](./VMT%20Reduction%20Mode%20Shift%20Final%20Report.pdf)     |
| Presentation to Transportation Policy Plan Advisory Workgroup, 12/16/2022 | [link](https://metrocouncil.org/Council-Meetings/Work-Groups/TPP-Advisory-Work-Group/2022/2022-12-16-TPP-Advisory-Work-Group-Meeting/2022-12-16-TPP-AWG-Presentation-VMT-Reduction-Mode.aspx) |
| Presentation to Transportation Policy Plan Technical Working Group, 9/14/2023    | [link](https://metrocouncil.org/Council-Meetings/Work-Groups/TPP-Technical-Working-Group/2023/2023-09-14-TPP-Technical-Working-Group-Meeting/2023-09-14-TPP-TWG-Presentation-VMT-Reduction-Maxi.aspx) |


The final PDF report is available - [VMT Reduction Mode Shift Final Report.pdf](./VMT%20Reduction%20Mode%20Shift%20Final%20Report.pdf)

## Repository details

Further details are available in READMEs within each subfolder.

* `src` Source code for main tools.  There are two:
	*  `routing` This tool creates the best car, walk, bike and transit path for each TBI trip. 
	*  `analysis_tool` The main analysis tool to calculate and summarize the results. 
* `data_processing` Scripts to process the TBI data.  Run these again if there is a new wave of the TBI. Must be run before the `analysis_tool`.
* `data_viz` A tool to visualize individual routes and check them for reasonableness.
* `reports` Several reports documenting the process. 

<br>
<details>
<summary>Notebook and environment instructions</summary>

The files here are mostly jupyter notebooks running python.  The installed packages used for development are stored in environment.yml.  You can use `conda` to set up the environment with the right installs:

	conda env create --file environment.yml

Then to activate the environment:

	conda activate vmtmodeenv

If you have difficulties solving packages on macOS, try using the Mac-specific environment. You may also need to finesse the 

	conda env create --file mac-environment.yml
	conda activate vmtmodeenv

After installing, if you are on a mac, we need to manually install jupyter notebook:

	pip install notebook

After installing the packages, you'll use keyring to set the main directory on our shared drive. See contact information below to get data access. 

	import keyring
	keyring.set_password("msp", "vmt_reduction_dir", <directory>)

</details>

## Data Management  

**Non-private and non-proprietary example data are the only data we store in this GitHub repository.**  The analyses used for this project are based on the Travel Behavior Inventory (TBI) which includes personal information for the respondents, including trip locations. For more information or to request data access, please contact us. 

| Input Data    | Access |
| -------- | ------- |
| Metropolitan Council Household Travel Behavior Inventory  | Direct acces provided by Council  |
| OpenStreetMap (OSM) network data | Direct access via python packages     |
| General Transit Feed Specification (GTFS)    | Provided by Metro Transit and other transit providers in the Twin Cities region |
| StreetLight Data speeds and volumes    | Accessed using the Metropolitan Council StreetLight subscription via the StreetLight API |

Please see our [DATA MANAGEMENT PLAN](DATA_MANAGEMENT_PLAN.md) for further details on our data practices for this project and the [final report](./VMT%20Reduction%20Mode%20Shift%20Final%20Report.pdf) appendices for more information. 


#### nbstripout

To avoid committing any identifiable data to the repository through Jupyter Notebooks outputs, we strip all outputs from notebooks before committing. *This needs to be set up on each machine accessing the git repository; this is a git security restriction to prevent arbitrary code execution without user consent when working with an untrusted clone.*

Full instructions are [available on the nbstripout site](https://github.com/kynan/nbstripout). In a nutshell, install nbstripout by running `pip install --upgrade nbstripout`, and then, within the repository directory, run `nbstripout --install`. This will remove outputs from notebooks when committing, without modifying your local files.

## Funding

This project was completed over 2022 and 2023. The University of Kentucky Research Foundation was selected through a competitive request for proposal process and compensated approximately $130,000 under contract 22P159. 

## Contacts

[Metropolitan Council](https://metrocouncil.org/)

- Primary contact: Liz Roten [email](liz.roten@metc.state.mn.us) @eroten
- Jonathan Ehrlich [email](jonathan.ehrlich@metc.state.mn.us) @JonathanEhrlichMC 
- Brandon Whited [email](brandon.whited@metc.state.mn.us) @Brandon-Whited

Researchers

- Greg Erhardt [email](greg.erhardt@uky.edu) @gregerhardt
- Matthew Wigginton Bhagat-Conway [email](mwbc@unc.edu) @mattwigway

Contributors
- Ashley Asmus @ashleyasmus
- Eric Lind @elindie
- Xu Zhang @xzh263
- Richard Donohue @rgdonohue

## Code of Conduct

Please note that the mode-shift project is released with a [Contributor Code of Conduct](CODE_OF_CONDUCT.md). By contributing to this project, you agree to abide by its terms.

![Metropolitan Council, University of Kentucky, and University of North Carolina at Chapel Hill logos](logos_combined.png)
