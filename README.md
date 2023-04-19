
# VMT Reduction and Mode Shift Study
This repository contains a collection of code supporting the mode shift feasibility study.

Do this to set up your repository/code: 

1. Clone the repository to your local machine. 
2. Copy the contents of the example directory to a working directory located outside the repository.  
3. Request access to the data stored on the Teams directory from @gregerhardt and create a path to the data directory. 
4. Run the script using the command: 

	```
	python run_all.py Usage: python run_all.py -d [DATA_DIR] -c [CONFIG_DIR] -o [OUTPUT_DIR]
	```

You may need to adjust the sys.path.append command in `run_all.py` to reference the source code within the repository. **It is important that no private data or outputs be stored in the repository.**  See Handling data for details.

This repository is in active development. See the [CONTRIBUTING](CONTRIBUTING.md) page on the right to learn how to contribute 🤝.

## Organization: what's here

* `src`: Source code for main processing scripts. 
* `example`: Example folder structure for running the scripts. 
  * `config`: Configurations and run options (i.e. user-set thresholds and rules)
  * `data`: Placeholder for input data. Only limited publicly available data should be stored here to test the system.  To run with real data, the user should instead point to a data folder on the Teams site.  See handling data. 
  * `output`: A placeholder for where output data would be written.  This is empty, and output data should be stored locally. 

## Install

The files here are mostly jupyter notebooks running python.  The installed packages used for development are stored in environment.yml.  You can use `conda` to set up the environment with the right installs:

	conda env create -n msp --file environment.yml

Then to activate the environment:

	conda activate msp

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

## Related repositories

[metc-tbi-helper](https://github.com/Metropolitan-Council/metc.tbi.helper) and metc-tbi-internal: These repositories create the data objects and .csv files containing the Travel Behavior Inventory (TBI) 2019 and 2021 data.

## Project info

### Management

[Asana board](https://app.asana.com/0/1203071874148265/board) available to project members.

Additional documents in VMT Reduction Mode Shift Microsoft Teams/Sharepoint.

### Contacts

Metropolitan Council 

- Ashley Asmus [email](ashley.asmus@metc.state.mn.us) @eroten
- Liz Roten [email](liz.roten@metc.state.mn.us) @ashleyasmus
- Eric Lind [email](eric.lind@metrotransit.org) @elindie
- Jonathan Ehrlich [email](jonathan.ehrlich@metc.state.mn.us) @JonathanEhrlichMC

University of Kentucky Team

- Greg Erhardt [email](greg.erhardt@uky.edu) @gregerhardt
- Xu Zhang [email](xuzhang_uk@uky.edu) @xzh263
- Richard Donohue [email](rgdonohue@uky.edu) @rgdonohue
- Matthew Wigginton Bhagat-Conway [email](mwbc@unc.edu) @mattwigway


## Code of Conduct

Please note that the mode-shift project is released with a [Contributor Code of Conduct](CODE_OF_CONDUCT.md). By contributing to this project, you agree to abide by its terms.

This repository is in active development. See [CONTRIBUTING](CONTRIBUTING.md) learn how to contribute 🤝.

![](logo.png)
