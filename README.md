
# VMT Reduction and Mode Shift Study
This repository contains a collection of code supporting the mode shift feasibility study.

Do this to set up your repository/code: 

1. Clone the repository to your local machine. 
2. Copy the contents of the example directory to a working directory located outside the repository.  
3. Request access to the data stored on the Teams directory from @gregerhardt and create a path to the data directory. 
4. Follow the install directions below.
 
**It is important that no private data or outputs be stored in the repository.**  See Handling data for details.

This repository is in active development. See the [CONTRIBUTING](CONTRIBUTING.md) page on the right to learn how to contribute 🤝.

## Organization: what's here

* `src` Source code for main tools.  There are two:
	*  `routing` This tool creates the best car, walk, bike and transit path for each TBI trip. 
	*  `analysis_tool` The main analysis tool to calculate and summarize the results. 
* `data_processing` Scripts to process the TBI data.  Run these again if there is a new wave of the TBI. Must be run before the `analysis_tool`.
* `data_viz` A tool to visualize individual routes and check them for reasonableness.
* `reports` Several reports documenting the process. 


## Install

The files here are mostly jupyter notebooks running python.  The installed packages used for development are stored in environment.yml.  You can use `conda` to set up the environment with the right installs:

	conda env create --file environment.yml

Then to activate the environment:

	conda activate vmtmodeenv

If you have difficulties solving packages on macOS, try using the Mac-specific environment.

	conda env create --file mac-environment.yml
	conda activate vmtmodeenv

After installing, if you are on a mac, we need to manually install jupyter notebook:

	pip install notebook

After installing the packages, you'll use keyring to set the main directory on our shared drive.  This avoids the need to hard-code file names in the scripts:

	import keyring
	keyring.set_password("msp", "vmt_reduction_dir", <directory>)



## Handling data

**Non-private and non-proprietary example data are the only data we store in this GitHub repository.**  The analyses used for this project are based on the Travel Behavior Inventory (TBI) which includes personal information for the respondents, including trip locations.  It is important to keep those data safe, including both the raw data and outputs of individual records or traces. Aggregated data summaries are ok. Users should take the following precautions: 

* Only run the scripts outside the repository to avoid accidentally checking in private data or outputs. 
* If you are working with a particular data file, add its extension to the .gitignore file. (This is redundant with the practice above, and that's the point.)

Eventually we hope to provide a runable example using synthetic and/or public data. If you think a new dataset should be incorporated, please discuss with the project contacts.

### nbstripout

We want to avoid inadvertently committing any identifiable data to the repository, and one way this could happen would be through outputs in Jupyter Notebooks. To prevent this, we strip all outputs from notebooks before committing. *This needs to be set up on each machine accessing the git repository; this is a git security restriction to prevent arbitrary code execution without user consent when working with an untrusted clone.*

Full instructions are [available on the nbstripout site](https://github.com/kynan/nbstripout). In a nutshell, install nbstripout by running `pip install --upgrade nbstripout`, and then, within the repository directory, run `nbstripout --install`. This will remove outputs from notebooks when committing, without modifying your local files.

I recommend using this as a failsafe, and using the "Clear All Outputs" menu item in JupyterLab before committing so that you are always committing clean files anyhow.

### Data Management Plan

Please see our [DATA MANAGEMENT PLAN](DATA_MANAGEMENT_PLAN.md)  for further details on our data practices for this project. 

## Related repositories

[metc-tbi-helper](https://github.com/Metropolitan-Council/metc.tbi.helper) and metc-tbi-internal: These repositories create the data objects and .csv files containing the Travel Behavior Inventory (TBI) 2019 and 2021 data.

## Project info

### Management

[Asana board](https://app.asana.com/0/1203071874148265/board) available to project members.

Additional documents in VMT Reduction Mode Shift Microsoft Teams/Sharepoint.

### Contacts

Metropolitan Council 

- Liz Roten [email](liz.roten@metc.state.mn.us) @eroten
- Jonathan Ehrlich [email](jonathan.ehrlich@metc.state.mn.us) @JonathanEhrlichMC 
- Brandon Whited [email](brandon.whited@metc.state.mn.us)

Researcher Contacts

- Greg Erhardt [email](greg.erhardt@uky.edu) @gregerhardt
- Matthew Wigginton Bhagat-Conway [email](mwbc@unc.edu) @mattwigway

Contributors
- Ashley Asmus @ashleyasmus
- Eric Lind @elindie
- Xu Zhang @xzh263
- Richard Donohue @rgdonohue

## Code of Conduct

Please note that the mode-shift project is released with a [Contributor Code of Conduct](CODE_OF_CONDUCT.md). By contributing to this project, you agree to abide by its terms.

This repository is in active development. See [CONTRIBUTING](CONTRIBUTING.md) learn how to contribute 🤝.

![](logo.png)
