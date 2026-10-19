import inspect
import json
import logging
from contextlib import contextmanager
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import steps
from settings import handler, scenario
from steps.enums import *
from util import (
    get_num_cold_starts,
    stacked_shift_histogram,
    total_shift_histogram,
    get_summary_df,
    get_duration_diff_df,
    bigger_markdown,
    format_figure,
    city_title_suffix,
    get_map_areas,
    ALL_CITIES,
)

# do conditional imports based on whether we are in build mode
# keyring/initialization is not necessary in build mode amd breaks things
try:
    from initialize import prepare_data
    import keyring
except ImportError as e:
    logging.error(
        "Unable to import keyring/prepare_data; if this is occurring and the program is not in build mode, something is wrong"
    )

    # only valid if in build mode
    if not handler["build"]:
        logging.exception(
            "Imports failed and program is not in build mode, something has gone wrong"
        )
        raise e
except Exception as e:
    logging.exception("Something has gone wrong with the import logic: %s", e)
    raise e


def reset_scenario() -> None:
    selected_scenario = st.session_state["selected_scenario"]
    for state_key in list(st.session_state):
        if state_key not in ("selected_scenario", "city"):
            del st.session_state[state_key]
    logging.info("Switching to scenario %s", selected_scenario)


def select_scenario() -> dict:
    scenario_names = list(handler["scenarios"])
    selected_scenario = st.sidebar.selectbox(
        "Scenario",
        scenario_names,
        index=scenario_names.index(handler["scenario_to_run"]),
        format_func=lambda name: f"{name}: {handler['scenarios'][name]['description']}",
        key="selected_scenario",
        on_change=reset_scenario,
    )
    return handler["scenarios"][selected_scenario]


def initialize_step(step_name: str) -> steps.parent_classes.BaseStep:
    step: steps.parent_classes.BaseStep = getattr(
        st.session_state.overall_step, step_name
    )(st.session_state.df)
    if step.is_continuous():
        extrema = step.get_extrema()
        configured_cutoff = handler.get("default_raw_cutoffs", {}).get(step_name)
        raw_cutoff = (
            float(configured_cutoff)
            if configured_cutoff is not None
            else min(
                max(float(step.get_cutoff_equivalent()), float(extrema[0])),
                float(extrema[1]),
            )
        )
        if configured_cutoff is not None:
            step.set_cutoff(raw_cutoff)
            step.set_cutoff_mode(CutoffMode.RAW)
        st.session_state.setdefault("default_raw_cutoffs", {})[step_name] = raw_cutoff
    return step


def apply_all_steps(phase: Phase, step_names: list[str]) -> None:
    """
    This function sets up the given phase and applies each named step with its current (default unless customized) cutoff.
    """
    setup_vars(phase)
    for step in step_names:
        curr = initialize_step(step)
        curr.apply_step()
        st.session_state.step_class_dict[step] = curr


def update_overall_shift() -> None:
    """
    This function marks trips that can shift to at least one mode in the current phase, saving the feasible pct for the probable phase.
    """
    df: pd.DataFrame = st.session_state.df
    phase = st.session_state.phase
    df.loc[:, f"{phase}_shift"] = (
        df[f"{phase}_transit_shift"]
        | df[f"{phase}_walk_shift"]
        | df[f"{phase}_bike_shift"]
    )

    if phase == Phase.FEASIBLE:
        st.session_state["feasible_pct"] = (
            df[(df[f"{phase}_shift"]) & (df["mode"] == Mode.CAR)]["vehicle_trips"].sum()
            / df[df["mode"] == Mode.CAR]["vehicle_trips"].sum()
        )


def run_all(phase: Phase) -> None:
    """
    This function is the helper for running all selected steps in a given phase.
    """

    # setup df if not done yet
    if "df" not in st.session_state:
        setup_df()

    # run through each selected step of the current phase
    if phase == Phase.FEASIBLE:
        apply_all_steps(phase, st.session_state.feasible_steps)
    elif phase == Phase.PROBABLE:
        apply_all_steps(phase, st.session_state.probable_steps)

    # toggle summary screen and refresh streamlit
    st.session_state["summary_screen"] = True
    st.rerun()


def run_all_defaults() -> None:
    """
    This function runs every feasible step and then every probable step with default values, ending on the probable summary.
    """
    logging.info("Running all feasible and probable steps with default values")
    st.session_state["feasible_steps"] = handler["feasible_steps"]
    st.session_state["probable_steps"] = handler["probable_steps"]
    filter_to_city()

    apply_all_steps(Phase.FEASIBLE, handler["feasible_steps"])
    update_overall_shift()
    apply_all_steps(Phase.PROBABLE, handler["probable_steps"])

    st.session_state.start_screen_feasible = False
    st.session_state.start_screen_probable = False
    st.session_state["summary_screen"] = True
    st.rerun()


def filter_to_city() -> None:
    """
    This function resets the working df to the full dataset, restricted to trips that begin or end in the selected city (if any).
    """
    df_full: pd.DataFrame = st.session_state.df_full
    city = st.session_state.get("city")
    if city is None:
        st.session_state["df"] = df_full.copy()
        return

    in_city = df_full["community"] == city
    if "d_community" in df_full.columns:
        in_city = in_city | (df_full["d_community"] == city)
    logging.info("Filtering to %s trips beginning or ending in %s", in_city.sum(), city)
    st.session_state["df"] = df_full[in_city].copy()


def start_screen_feasible() -> None:
    """
    This function generates the start screen for the feasible phase.
    """

    # title
    st.title("Configure the feasible phase")

    # feasible vs. probable blurb
    bigger_markdown(
        "The feasible phase involves steps that determine whether a trip can feasibly shift to a given mode or not. In contrast, the probable phase, which follows the feasible phase, places more restrictions on the already feasible trips to determine whether a trip can shift to a mode with likelihood."
    )

    st.markdown("***")

    run_choice = st.radio(
        "How do you want to run the tool?",
        [
            "Run all feasible and probable steps with default values",
            "Customize steps and values",
        ],
    )

    # city picker; filters trips (and their routes) to those whose origin or destination is in the chosen CTU
    df_full: pd.DataFrame = st.session_state.df_full
    has_destination = "d_community" in df_full.columns
    cities = set(df_full["community"]) | (
        set(df_full["d_community"]) if has_destination else set()
    )
    city_options = [ALL_CITIES] + sorted(cities - {"na"})
    current_city = st.session_state.get("city") or ALL_CITIES
    selected_city = st.selectbox(
        "Only include trips that begin or end in this city",
        city_options,
        index=city_options.index(current_city) if current_city in city_options else 0,
    )
    st.session_state["city"] = None if selected_city == ALL_CITIES else selected_city
    if not has_destination:
        st.warning(
            "The saved data has no destination cities; only trips beginning in the selected city will be included. Reinitialize the data to add destinations."
        )

    # define all actions that can be done
    st.sidebar.header("Actions")

    if run_choice.startswith("Run all"):
        bigger_markdown(
            "Clicking <strong>Run all steps with default values</strong> at the left will apply every feasible step and then every probable step with their default values and go straight to the probable summary."
        )
        if st.sidebar.button("Run all steps with default values"):
            run_all_defaults()
        return

    st.markdown("***")

    # explanation for checkmarks
    bigger_markdown(
        inspect.cleandoc(
            """The checked steps will be able to be run in the visualization tool. There should be at least one step checked before beginning, but ideally, one step that applies to each mode should be checked for meaningful overall results. 
                
    At the left, <strong>Begin customization with selected steps</strong> walks through the checked steps one at a time so you can set each cutoff, <strong>Begin customization with all steps</strong> does the same for every step regardless of what is checked, and <strong>Run selected steps with default values</strong> applies the checked steps with their default cutoffs and goes straight to the summary."""
        )
    )

    # create feasible_steps session state array if not present as well as a scenarios dictionary
    if "feasible_steps" not in st.session_state:
        st.session_state["feasible_steps"] = []
        st.session_state["scenarios"] = {mode: "none" for mode in Mode.get_all()}

    # begin visualization tools with selected steps
    if st.sidebar.button("Begin customization with selected steps"):
        logging.info("Beginning tool with selected steps")

        # filter to the selected city, setup variables, toggle start screen feasible off, and refresh
        filter_to_city()
        setup_vars(Phase.FEASIBLE)
        st.session_state.start_screen_feasible = False
        st.rerun()

    # begin visualization with all steps selected by default
    if st.sidebar.button("Begin customization with all steps"):
        logging.info("Beginning tool with all steps")

        # set feasible steps to all defined feasible steps
        st.session_state["feasible_steps"] = handler["feasible_steps"]

        # filter to the selected city, setup variables/toggle start screen feasible off and refresh
        filter_to_city()
        setup_vars(Phase.FEASIBLE)
        st.session_state.start_screen_feasible = False
        st.rerun()

    # run all selected steps automatically
    if st.sidebar.button("Run selected steps with default values"):
        logging.info("Running through all steps automatically")

        # toggle start screen, filter to the selected city & call the run all function for feasible
        st.session_state.start_screen_feasible = False
        filter_to_city()
        run_all(Phase.FEASIBLE)

    # create the multiselect to choose steps
    # NOTE: this can sometimes be buggy if you don't click off the multiselect before running it, as the session state sometimes takes a bit to fully respond to user input
    st.session_state["feasible_steps"] = st.multiselect(
        "Choose the feasible steps to run", handler["feasible_steps"]
    )

    # overriding this scenario approach to use separate files instead.
    # create the scenario picker; scenarios are persisted throughout the entire application
    # bigger_markdown("Choose the scenarios to run for each mode. Choosing 'default' will not run any scenarios for the mode.")
    # col1, col2, col3, col4 = st.columns(4)
    #
    # with col1:
    #    st.session_state["scenarios"][Mode.CAR] = st.radio("Choose the car scenario:", [x[0] for x in handler["scenario_columns"][Mode.CAR]])
    #
    # with col2:
    #    st.session_state["scenarios"][Mode.WALK] = st.radio("Choose the walk scenario:", [x[0] for x in handler["scenario_columns"][Mode.WALK]])
    #
    # with col3:
    #    st.session_state["scenarios"][Mode.BIKE] = st.radio("Choose the bike scenario:", [x[0] for x in handler["scenario_columns"][Mode.BIKE]])
    #
    # with col4:
    #    st.session_state["scenarios"][Mode.TRANSIT] = st.radio("Choose the transit scenario:", [x[0] for x in handler["scenario_columns"][Mode.TRANSIT]])


def start_screen_probable() -> None:
    """
    This function generates the start screen for the probable step.
    """

    # title
    st.title("Configure the probable steps")

    # feasible vs. probable blurb
    bigger_markdown(
        "The feasible phase involves steps that determine whether a trip can feasibly shift to a given mode or not. In contrast, the probable phase, which follows the feasible phase, places more restrictions on the already feasible trips to determine whether a trip can shift to a mode with likelihood."
    )

    st.markdown("***")

    # explanation of checkmarks
    bigger_markdown(
        inspect.cleandoc(
            """The checked steps will be able to be run in the visualization tool. There should be at least one step checked before beginning, but ideally, one step that applies to each mode should be checked for meaningful overall results. 
                
    At the left, <strong>Begin customization with selected steps</strong> walks through the checked steps one at a time so you can set each cutoff, <strong>Begin customization with all steps</strong> does the same for every step regardless of what is checked, and <strong>Run selected steps with default values</strong> applies the checked steps with their default cutoffs and goes straight to the summary."""
        )
    )

    # init probable steps array if not already present
    if "probable_steps" not in st.session_state:
        st.session_state["probable_steps"] = []

    # define all the possible actions you can do at this point
    st.sidebar.header("Actions")

    # begin with selected steps; setup probable variables & toggle off this start screen & refresh
    if st.sidebar.button("Begin customization with selected steps"):
        logging.info("Beginning tool with selected steps")
        if "phase" not in st.session_state or st.session_state.phase != Phase.PROBABLE:
            setup_vars(Phase.PROBABLE)
        st.session_state.start_screen_probable = False
        st.rerun()

    # begin with all steps selected; set probable steps to all probable steps & toggle off this start screen & refresh
    if st.sidebar.button("Begin customization with all steps"):
        logging.info("Beginning tool with all steps")

        st.session_state["probable_steps"] = handler["probable_steps"]
        if "phase" not in st.session_state or st.session_state.phase != Phase.PROBABLE:
            setup_vars(Phase.PROBABLE)
        st.session_state.start_screen_probable = False
        st.rerun()

    # run through all selected steps automatically
    if st.sidebar.button("Run selected steps with default values"):
        logging.info("Running through all steps automatically")

        # toggle off this start screen & call the run all function with the probable phase
        st.session_state.start_screen_probable = False
        run_all(Phase.PROBABLE)

    # create the multiselect to choose the probable steps to run
    # NOTE: like with feasible steps, this can also be buggy sometimes
    st.session_state["probable_steps"] = st.multiselect(
        "Choose the probable steps to run", handler["probable_steps"]
    )


def setup_df() -> 0:
    """
    This function reads in/sets up the input dataframe for the visualization tool.
    """

    # if we are in build mode, turn off logging; otherwise, send logs to output/
    if handler["build"]:
        logger = logging.getLogger()
        logger.disabled = True
    else:
        logging.getLogger().setLevel("INFO")
        logging.basicConfig(
            filename="output/streamlit.log",
            filemode="w",
            format="%(name)s - %(levelname)s - %(message)s",
        )

    # if we are forcing reinitialization and we are not in build mode, reinitialize
    if handler["force_reinitialize"] and not handler["build"]:
        logging.info("Rebuilding data from raw inputs")

        # read in data & pipe it through the cleaning function
        drive_data_dir = keyring.get_password("msp", "vmt_reduction_dir")
        raw = pd.read_csv(
            drive_data_dir + scenario["input_tbi_file"], usecols=handler["keep_columns"]
        )
        df = prepare_data(raw, drive_data_dir, scenario)
    # otherwise, we are not reinitialization -- read in precleaned files
    else:
        logging.info("Attempting to read in pre-cleaned data files")

        # try to read in file specified as saved_tbi_file (supporting parquet/csv)
        try:
            if scenario["saved_tbi_file"].split(".")[-1] == "parquet":
                logging.info("Reading in the specified parquet file")
                df = pd.read_parquet(scenario["saved_tbi_file"])
            elif scenario["saved_tbi_file"].split(".")[-1] == "csv":
                logging.info("Reading in the specified csv file")
                df = pd.read_csv(scenario["saved_tbi_file"])

        # if we cannot read the input, try rebuilding, but if we are in build mode, raise an exception
        except Exception as e:
            logging.info(
                "Something has gone wrong reading in the pre-cleaned data files: %s", e
            )
            if handler["build"]:
                logging.exception("Unable to rebuild data in build mode")
                raise e
            logging.info("Attempting to rebuild inputs manually from scratch")
            drive_data_dir = keyring.get_password("msp", "vmt_reduction_dir")
            raw = pd.read_csv(
                drive_data_dir + scenario["input_tbi_file"],
                usecols=handler["keep_columns"],
            )

            df = prepare_data(raw, drive_data_dir, scenario)

    # store the generated df into a session state variable
    logging.info("Setting up the data inputs has succeeded")
    st.session_state["df_full"] = df
    st.session_state["df"] = df

    return 0


def setup_vars(phase: Phase) -> None:
    """This function sets up the variables for the passed in phase.

    Args:
        phase (Phase): the phase whose variables should be set up
    """
    logging.info("Setting up variables for phase %s", phase)

    # if we are in the probable phase, make df the subset of trips that can feasibly shift, according to the probable phase logic
    if phase == Phase.PROBABLE:
        # keep the finished feasible phase so the summary can show it alongside the probable phase
        if st.session_state.get("phase") == Phase.FEASIBLE:
            st.session_state["feasible_snapshot"] = (
                st.session_state.df,
                st.session_state.step_class_dict,
            )
        st.session_state["df"] = st.session_state.df.loc[
            st.session_state.df["feasible_shift"], :
        ].copy()
    else:
        st.session_state.pop("feasible_snapshot", None)

    # have a handy short-hand alias for the session state dataframe variable
    df: pd.DataFrame = st.session_state.df

    # everything is feasible/probable initially
    df[f"{phase}_{Mode.WALK}_shift"] = True
    df[f"{phase}_{Mode.BIKE}_shift"] = True
    df[f"{phase}_{Mode.TRANSIT}_shift"] = True
    df[f"{phase}_shift"] = True

    # change the current phase stored in session state
    st.session_state["phase"] = phase

    # try to setup some initial step/overall_step logic using the feasible/probable step list we are working with
    # if no steps were selected, indexing to 0 is impossible, and this raises an error
    try:
        if phase == Phase.FEASIBLE:
            st.session_state["step"] = st.session_state["feasible_steps"][0]
            st.session_state["overall_step"] = steps.feasible_steps
        elif phase == Phase.PROBABLE:
            st.session_state["step"] = st.session_state["probable_steps"][0]
            st.session_state["overall_step"] = steps.probable_steps
        else:
            logging.exception(
                "Something went wrong with the phase enum: %s",
                st.session_state.overall_step,
            )
            raise RuntimeError("Something went wrong with the phase enum")
    except IndexError as e:
        logging.exception(
            "no steps selected in the initial start page -- need to restart program"
        )
        raise RuntimeError(
            "No steps selected in initial start page -- refresh to restart the tool"
        )

    # create a dictionary for storing initialized step class objects and store the first step within it already
    st.session_state["step_class_dict"] = dict()
    st.session_state["step_class_dict"][st.session_state.step] = initialize_step(
        st.session_state.step
    )

    # store the current step class (as an alias to the stored one in the dictionary)
    st.session_state["step_class"] = st.session_state["step_class_dict"][
        st.session_state.step
    ]
    # turn off the summary screen (want to show the normal step screen right now)
    st.session_state["summary_screen"] = False


def final_summary() -> None:
    """
    This function generates the final summary for the visualization tool.
    """
    st.session_state["summary_tables"] = {}

    # define the actions we can do at this point
    st.sidebar.header("Actions")

    # button to allow shift to feasible step; only possible if currently in feasible and probable not disabled
    if st.session_state.phase == Phase.FEASIBLE:
        if st.sidebar.button("Continue to probable phase"):
            logging.info("Moving to probable step")
            st.session_state.summary_screen = False
            st.session_state.start_screen_probable = True
            st.rerun()

    # save reference to underlying df for ease of typing
    df: pd.DataFrame = st.session_state.df

    # rerun current phase from step selection
    if st.sidebar.button("Restart this phase"):
        logging.info("Rerunning current (%s) phase of the tool", st.session_state.phase)

        # turn off the summary screen and turn on the desired start screen and refresh
        st.session_state.summary_screen = False
        if st.session_state.phase == Phase.FEASIBLE:
            st.session_state.start_screen_feasible = True
        elif st.session_state.phase == Phase.PROBABLE:
            st.session_state.start_screen_probable = True
        st.rerun()

    # currently not supported to go back all the way--can just refresh to do so
    if st.sidebar.button("Start over from the beginning", disabled=True):
        pass

    # calculate overall shift ability -- can shift to at least one mode; saves feasible pct for the probable phase
    update_overall_shift()

    # summary just has some overall statistics
    st.title(f"Summary{city_title_suffix()}")
    st.subheader(f"{scenario['description']}")

    snapshot = st.session_state.get("feasible_snapshot")
    if st.session_state.phase == Phase.PROBABLE and snapshot is not None:
        render_toc([Phase.FEASIBLE, Phase.PROBABLE])
        st.header("Feasible phase", anchor=f"{Phase.FEASIBLE}-phase", divider=True)
        with phase_state(snapshot[0], Phase.FEASIBLE, snapshot[1]):
            phase_summary()
        st.header("Probable phase", anchor=f"{Phase.PROBABLE}-phase", divider=True)
        phase_summary()
    else:
        render_toc([st.session_state.phase])
        phase_summary()

    if not handler["build"] and st.sidebar.button("Save results"):
        with st.spinner("Exporting results, summary tables, and options"):
            city = st.session_state.get("city") or ALL_CITIES
            output_paths = {
                key: Path(scenario[key])
                for key in ("saved_results", "saved_options", "saved_tables")
            }
            if city != ALL_CITIES:
                output_paths = {
                    key: path.parent / city / path.name
                    for key, path in output_paths.items()
                }
            for path in output_paths.values():
                path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_paths["saved_results"], index=False)
            phase_steps = {}
            if st.session_state.phase == Phase.PROBABLE and snapshot is not None:
                phase_steps[Phase.FEASIBLE.value] = snapshot[1]
            phase_steps[st.session_state.phase.value] = st.session_state.step_class_dict
            options = {
                phase: {
                    step_name: {
                        "cutoff": (
                            step_class.get_cutoff()
                            if step_class.is_continuous()
                            else None
                        ),
                        "cutoff_mode": (
                            str(step_class.get_cutoff_mode())
                            if step_class.is_continuous()
                            else "categorical"
                        ),
                    }
                    for step_name, step_class in step_classes.items()
                }
                for phase, step_classes in phase_steps.items()
            }
            options["city"] = city
            with open(
                output_paths["saved_options"], "w", encoding="utf-8"
            ) as options_file:
                json.dump(options, options_file, indent=2)
            with open(
                output_paths["saved_tables"], "w", encoding="utf-8"
            ) as tables_file:
                json.dump(
                    {
                        "scenario": st.session_state.get(
                            "selected_scenario", handler["scenario_to_run"]
                        ),
                        "phases": st.session_state["summary_tables"],
                    },
                    tables_file,
                    indent=2,
                )
        st.success("Saved results CSV, summary tables JSON, and options JSON.")


SUMMARY_SECTIONS = [
    "Any mode",
    "Walking",
    "Biking",
    "Transit",
    "Geography",
    "Raw metrics",
    "Shifts by categories",
    "Tour-level shifts",
]


def section_anchor(phase: Phase, title: str) -> str:
    """Returns the unique page anchor for a summary section within a phase."""
    return f"{phase}-{title.lower().replace(' ', '-')}"


def section_header(title: str) -> None:
    """Renders a summary section header with an anchor the table of contents can link to."""
    st.subheader(title, anchor=section_anchor(st.session_state.phase, title))


def render_toc(phases: list[Phase]) -> None:
    """Renders a fixed table of contents on the right side of the page linking to each phase's summary sections."""
    links = []
    for phase in phases:
        if len(phases) > 1:
            links.append(
                f'<a class="toc-phase" href="#{phase}-phase">{str(phase).capitalize()} phase</a>'
            )
        links += [
            f'<a class="toc-section" href="#{section_anchor(phase, title)}">{title}</a>'
            for title in SUMMARY_SECTIONS
        ]
    st.markdown(
        f'<nav class="toc"><strong>Contents</strong>{"".join(links)}</nav>',
        unsafe_allow_html=True,
    )


@contextmanager
def phase_state(df: pd.DataFrame, phase: Phase, step_class_dict: dict):
    """
    This context manager temporarily points the session state at another phase's results so phase_summary can render them.
    """
    saved = {key: st.session_state[key] for key in ("df", "phase", "step_class_dict")}
    st.session_state.update(df=df, phase=phase, step_class_dict=step_class_dict)
    try:
        yield
    finally:
        st.session_state.update(saved)


def register_summary_table(name: str, table: pd.DataFrame) -> pd.DataFrame:
    """Store a JSON-safe split representation of a displayed summary table."""
    phase = st.session_state.phase.value
    tables = st.session_state.setdefault("summary_tables", {})
    tables.setdefault(phase, {})[name] = json.loads(
        table.to_json(orient="split", date_format="iso")
    )
    return table


def phase_summary() -> None:
    """
    This function generates the summary statistics, tables, and figures for the phase currently in session state.
    """
    df: pd.DataFrame = st.session_state.df

    # which adjective to use (depends on phase)
    adjective = (
        "feasibly" if st.session_state.phase == Phase.FEASIBLE else "with likelihood"
    )

    # total trips is the # of car trips total
    total_trips = df[df["mode"] == Mode.CAR]["vehicle_trips"].sum()

    # tell the % of people that can shift to any mode and to individual modes
    bigger_markdown(
        f"Overall, <strong>{len(st.session_state.step_class_dict)}</strong> steps were run, and, accounting for these restrictions, <strong>{df[(df[f'{st.session_state.phase}_shift']) & (df['mode'] == Mode.CAR)]['vehicle_trips'].sum() / total_trips * 100:.1f}%</strong> of all trips could shift {adjective} from car to some non-car mode. When considering individual mode shifts, <strong>{df[(df[f'{st.session_state.phase}_transit_shift']) & (df['mode'] == Mode.CAR)]['vehicle_trips'].sum() / total_trips * 100:.1f}%</strong> of trips could shift {adjective} to transit, <strong>{df[(df[f'{st.session_state.phase}_walk_shift']) & (df['mode'] == Mode.CAR)]['vehicle_trips'].sum() / total_trips * 100:.1f}%</strong> to bike, and <strong>{df[(df[f'{st.session_state.phase}_bike_shift']) & (df['mode'] == Mode.CAR)]['vehicle_trips'].sum() / total_trips * 100:.1f}%</strong> to bike."
    )

    # record of settings for all steps that were run
    bigger_markdown(
        "Below are the steps that were run and their settings (1 for categoricals indicates that it was run)."
    )
    settings = {}
    # iterate over saved step class objects
    for name, step_class in st.session_state.step_class_dict.items():
        # last run
        prev = step_class.get_previous_run()
        # don't show if it was disabled/never run
        if prev == None:
            continue
        # logic to format things correctly
        if step_class.is_continuous():
            if prev[1] == CutoffMode.PCT:
                settings[name] = (
                    f"{prev[0] * 100:.2f}th pct ({step_class.get_pct_value(prev[0]):.1f} {step_class.get_units()})"
                )
            elif prev[1] == CutoffMode.RAW:
                settings[name] = f"{prev[0]:.2f} {step_class.get_units()}"
            else:
                raise RuntimeError("Something went wrong with the cutoff mode enum")
        else:
            settings[name] = "1 (categorical)"
    register_summary_table(
        "step_settings",
        pd.DataFrame.from_dict(settings, orient="index", columns=["Setting"]),
    )
    st.write(settings)

    section_header("Any mode")

    # overall % of trips/vmt that can shift given the run constraints
    # NOTE: the overall %s will be 100% if some mode had no applicable steps run (since there was no restriction on shifting to that)
    bigger_markdown(
        r"Below, the % of car trips/VMT that can shift to the 3 modes/any non-car mode can be seen in table form."
    )
    overall_shifts = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    overall_shifts["Feasible to switch to walk"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_walk_shift"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_walk_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100: .1f}%',
    ]
    overall_shifts["Feasible to switch to bike"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_bike_shift"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_bike_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    overall_shifts["Feasible to switch to transit"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_transit_shift"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_transit_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    overall_shifts["Feasible to switch to any non-car mode"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    st.table(register_summary_table("overall_shifts", overall_shifts))

    # fastest alternative by mode comparisons
    bigger_markdown(
        r"Below, the distribution of the duration difference between the best non-car mode and car for shifted trips is shown. Note: a trip can only have a fastest mode if there is a mode that is feasible/likely for it take."
    )
    df["transit_duration_seconds_na"] = (
        df["transit_duration"].fillna(9999999) * 60
    )  # if no transit trip found, make it very slow to allow other modes to beat it

    # mode must be feasible to be the minimum alternative mode duration
    df["feasible_walk_duration_seconds"] = np.where(
        df[f"{st.session_state.phase}_walk_shift"], df["walk_duration_seconds"], 9999999
    )
    df["feasible_bike_duration_seconds_adj"] = np.where(
        df[f"{st.session_state.phase}_bike_shift"],
        df["bike_duration_seconds_adj"],
        9999999,
    )
    df["feasible_transit_duration_seconds_na"] = np.where(
        df[f"{st.session_state.phase}_transit_shift"],
        df["transit_duration_seconds_na"],
        9999999,
    )

    df["min_feasible_alt_mode_duration"] = df[
        [
            "feasible_transit_duration_seconds_na",
            "feasible_bike_duration_seconds_adj",
            "feasible_walk_duration_seconds",
        ]
    ].min(axis=1)

    df["fastest_mode"] = "na"
    df["fastest_mode"] = np.where(
        (df[f"{st.session_state.phase}_walk_shift"])
        & (
            df["walk_duration_seconds"] == df["min_feasible_alt_mode_duration"]
        ),  # is fastest if it is the previously calculated minimum
        Mode.WALK,
        df["fastest_mode"],
    )
    df["fastest_mode"] = np.where(
        (df[f"{st.session_state.phase}_bike_shift"])
        & (
            df["bike_duration_seconds_adj"] == df["min_feasible_alt_mode_duration"]
        ),  # is fastest if it is the previously calculated minimum
        Mode.BIKE,
        df["fastest_mode"],
    )
    df["fastest_mode"] = np.where(
        (df[f"{st.session_state.phase}_transit_shift"])
        & (
            df["transit_duration_seconds_na"] == df["min_feasible_alt_mode_duration"]
        ),  # is fastest if it is the previously calculated minimum
        Mode.TRANSIT,
        df["fastest_mode"],
    )

    # for histograms, calculate difference evenw hen not feasible
    df["min_alt_mode_duration"] = df[
        [
            "transit_duration_seconds_na",
            "bike_duration_seconds_adj",
            "walk_duration_seconds",
        ]
    ].min(axis=1)
    df["min_alt_mode_duration"] = np.where(
        df["fastest_mode"] == "na",
        df["min_alt_mode_duration"],
        df["min_feasible_alt_mode_duration"],
    )

    # create a table of the % of car trips/vmt that shifts to each/any mode can mitigate
    overall_shift_comparison = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    overall_shift_comparison["Walk is the fastest alternative"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.WALK)]["vehicle_trips"].sum() / df[df["mode"] == Mode.CAR]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.WALK)]["vmt"].sum() / df[df["mode"] == Mode.CAR]["vmt"].sum() * 100:.1f}%',
    ]
    overall_shift_comparison["Bike is the fastest alternative"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.BIKE)]["vehicle_trips"].sum() / df[df["mode"] == Mode.CAR]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.BIKE)]["vmt"].sum() / df[df["mode"] == Mode.CAR]["vmt"].sum() * 100:.1f}%',
    ]
    overall_shift_comparison["Transit is the fastest alternative"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.TRANSIT)]["vehicle_trips"].sum() / df[df["mode"] == Mode.CAR]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df["fastest_mode"] == Mode.TRANSIT)]["vmt"].sum() / df[df["mode"] == Mode.CAR]["vmt"].sum() * 100:.1f}%',
    ]
    overall_shift_comparison["Feasible to switch to any non-car mode"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    st.table(
        register_summary_table("overall_shift_comparison", overall_shift_comparison)
    )

    # histogram for min travel time difference for all modes
    bigger_markdown(
        r"Below, the distribution of the duration difference between the best non-car mode and car for shifted trips is shown"
    )
    fig1 = total_shift_histogram(df, st.session_state.phase)
    st.plotly_chart(format_figure(fig1))

    # table for fastest alternative mode being within x minutes of driving
    bigger_markdown(
        f"The % of car trips and VMT that are {st.session_state.phase} and within x minutes from the fastest alternative mode can be seen in the below table."
    )
    df["min_alt_mode_minus_car_duration"] = (
        df["min_feasible_alt_mode_duration"] - df["car_duration_seconds_adj"]
    ) / 60
    duration_diff_df = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    duration_diff_df["Fastest mode is within 5 minutes of driving"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"]) & (df["min_alt_mode_minus_car_duration"] <= 5)]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"]) & (df["min_alt_mode_minus_car_duration"] <= 5)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    duration_diff_df["Fastest mode is within 15 minutes of driving"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"]) & (df["min_alt_mode_minus_car_duration"] <= 15)]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"]) & (df["min_alt_mode_minus_car_duration"] <= 15)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    duration_diff_df["Fastest mode is within 30 minutes of driving"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"]) & (df["min_alt_mode_minus_car_duration"] <= 30)]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100: .1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift"]) & (df["min_alt_mode_minus_car_duration"] <= 30)]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    st.table(register_summary_table("duration_diff_df", duration_diff_df))
    fastest_15_minute_column = "Fastest mode is within 15 minutes of driving"
    car_trip_share = duration_diff_df.loc[
        r"% of Car Trips", fastest_15_minute_column
    ].strip()
    vmt_share = duration_diff_df.loc[r"% of VMT", fastest_15_minute_column].strip()
    selected_city = st.session_state.get("city")
    region = selected_city or "the Twin Cities region"
    bigger_markdown(
        f"Overall, in {region} today, {car_trip_share} of car trips could shift to walk, bike or transit with travel times within 15 minutes of driving, and these trips represent {vmt_share} of VMT."
    )

    # details about walking shifts
    section_header("Walking")

    # calculate minutes for future reference
    df["walk_duration_minutes"] = df["walk_duration_seconds"] / 60

    # get % trips and vmt for each walk step and for overall shifts to walking
    bigger_markdown(
        r"Below, a table detailing processed steps and the % of car trips and VMT that meet those constraints can be seen."
    )
    st.table(
        register_summary_table(
            "walk_step_summary",
            get_summary_df(
                df,
                st.session_state.step_class_dict.values(),
                Mode.WALK,
                f"{st.session_state.phase}_walk_shift",
                st.session_state.phase,
            ),
        )
    )

    # stacked histogram of duration difference for feasible drive, non-feasible drive, and walk trips
    bigger_markdown(
        "Below, a stacked histogram detailing the travel time difference distributions for drive trips that can feasibly shift to walk, drive trips that can't shift, and observed walk trips can be seen."
    )

    st.plotly_chart(
        format_figure(
            stacked_shift_histogram(
                df,
                Mode.WALK,
                "walk_duration_minutes",
                f"{st.session_state.phase}_walk_shift",
                st.session_state.phase,
            )
        )
    )

    # get df of the % of trips/vmt that are within x minutes of walking
    bigger_markdown(
        f"The % of car trips and VMT that are {st.session_state.phase} and within x minutes from walking can be seen in the below table."
    )
    st.table(
        register_summary_table(
            "walk_duration_summary",
            get_duration_diff_df(
                df,
                Mode.WALK,
                f"{st.session_state.phase}_walk_shift",
                "walk_duration_minutes",
            ),
        )
    )

    # details about biking shifts
    section_header("Biking")

    # get minutes for future reference
    df["bike_duration_minutes_adj"] = df["bike_duration_seconds_adj"] / 60

    # get % trips and vmt for each walk step and for overall shifts to biking
    bigger_markdown(
        r"Below, a table detailing processed steps and the % of car trips and VMT that meet those constraints can be seen."
    )
    st.table(
        register_summary_table(
            "bike_step_summary",
            get_summary_df(
                df,
                st.session_state.step_class_dict.values(),
                Mode.BIKE,
                f"{st.session_state.phase}_bike_shift",
                st.session_state.phase,
            ),
        )
    )

    # stacked histogram of duration difference for feasible drive, non-feasible drive, and bike trips
    bigger_markdown(
        "Below, a stacked histogram detailing the travel time difference distributions for drive trips that can feasibly shift to biking, drive trips that can't shift, and observed biking trips can be seen."
    )

    st.plotly_chart(
        format_figure(
            stacked_shift_histogram(
                df,
                Mode.BIKE,
                "bike_duration_minutes_adj",
                f"{st.session_state.phase}_bike_shift",
                st.session_state.phase,
            )
        )
    )

    # get df of the % of trips/vmt that are within x minutes of biking
    bigger_markdown(
        f"The % of car trips and VMT that are {st.session_state.phase} and within x minutes from walking can be seen in the below table."
    )
    st.table(
        register_summary_table(
            "bike_duration_summary",
            get_duration_diff_df(
                df,
                Mode.BIKE,
                f"{st.session_state.phase}_bike_shift",
                "bike_duration_minutes_adj",
            ),
        )
    )

    # details about biking shifts
    section_header("Transit")

    # get % trips and vmt for each transit step and for overall shifts to transit
    bigger_markdown(
        r"Below, a table detailing processed steps and the % of car trips and VMT that meet those constraints can be seen."
    )
    st.table(
        register_summary_table(
            "transit_step_summary",
            get_summary_df(
                df,
                st.session_state.step_class_dict.values(),
                Mode.TRANSIT,
                f"{st.session_state.phase}_transit_shift",
                st.session_state.phase,
            ),
        )
    )

    # stacked histogram of duration difference for feasible drive, non-feasible drive, and transit trips
    bigger_markdown(
        "Below, a stacked histogram detailing the travel time difference distributions for drive trips that can feasibly shift to transit, drive trips that can't shift, and observed transit trips can be seen. NOTE: due to the need to filter out trips with no valid transit trip (and thus no applicable transit duration), there are no infeasible drive trips within this histogram."
    )

    st.plotly_chart(
        format_figure(
            stacked_shift_histogram(
                df[
                    (~df["transit_duration"].isna())
                    & (df["transit_duration"] > 0)
                    & (df["transit_duration"] < 1440)
                ],
                Mode.TRANSIT,
                "transit_duration",
                f"{st.session_state.phase}_transit_shift",
                st.session_state.phase,
            )
        )
    )

    # get df of the % of trips/vmt that are within x minutes of transit
    bigger_markdown(
        f"The % of car trips and VMT that are {st.session_state.phase} and within x minutes from transit can be seen in the below table."
    )
    st.table(
        register_summary_table(
            "transit_duration_summary",
            get_duration_diff_df(
                df[~df["transit_duration"].isna()],
                Mode.TRANSIT,
                f"{st.session_state.phase}_transit_shift",
                "transit_duration",
            ),
        )
    )

    # various maps showing how metrics are distributed across geographies
    section_header("Geography")

    # map of the % of trips in each community regino that can shift given the restrictions

    # get a dummy communities df with a column for the proportion of people that could shift in an area
    map_areas, communities = get_map_areas(df)
    community_pct = (
        df.assign(community=map_areas)
        .groupby(["community", f"{st.session_state.phase}_shift"])[["vehicle_trips"]]
        .sum()
        .reset_index()
    )
    community_pct["percent_vehicle_trips"] = community_pct[
        "vehicle_trips"
    ] / community_pct.groupby("community")["vehicle_trips"].transform("sum")
    community_pct.set_index("community", inplace=True)
    values = community_pct[community_pct[f"{st.session_state.phase}_shift"] == 1][
        "percent_vehicle_trips"
    ].fillna(0)
    communities[f"Percent of vehicle trips that can shift {adjective}"] = values

    # create a choropleth mapbox using this (use mapbox since this allows for the desired projection)
    bigger_markdown(
        f"This map shows the percent of vehicle trips in each community region that can {adjective} shift to any alternative non-car mode."
    )
    fig2 = px.choropleth_map(
        communities,
        geojson=communities.geometry,
        locations=communities.index,
        color=f"Percent of vehicle trips that can shift {adjective}",
        range_color=(0, 1),
        color_continuous_scale="viridis_r",
        map_style="carto-positron",
        center={"lat": 44.9778, "lon": -93.2650},
        zoom=7.5,
        opacity=0.8,
    )
    fig2.update_layout(
        margin=dict(l=0, r=0, b=0, t=40),
        width=900,
        height=500,
        title=dict(
            text=f"Percent of vehicle trips in that can shift {adjective} to any non-car mode",
            x=0,
            y=0.98,
            yanchor="top",
            xanchor="left",
        ),
    )
    fig2.update_coloraxes(
        colorbar_title_text=f"Percent of<br>vehicle trips<br>that can shift<br>{adjective}",
        colorbar_tickformat="0%",
    )
    fig2.update_geos(fitbounds="locations", visible=False)
    fig2.update_traces(
        hovertemplate=f"<b>%{{location}}</b><br>Can shift {adjective}: %{{z:.1%}}<extra></extra>"
    )
    st.plotly_chart(format_figure(fig2))

    # map of % of trips in each community regino that can shift competitively when considering the fastest alternative mode

    # use previously used dummy communities df to store this metric for each geography
    df["competitive_timing"] = df["min_alt_mode_minus_car_duration"] <= 15

    community_pct = (
        df.assign(community=map_areas)
        .groupby(["community", "competitive_timing"])[["vehicle_trips"]]
        .sum()
        .reset_index()
    )
    community_pct["percent_vehicle_trips"] = community_pct[
        "vehicle_trips"
    ] / community_pct.groupby("community")["vehicle_trips"].transform("sum")
    community_pct.set_index("community", inplace=True)
    values_competitive = community_pct[community_pct["competitive_timing"] == 1][
        "percent_vehicle_trips"
    ].fillna(0)
    communities[f"Percent of vehicle trips that can shift {adjective}"] = (
        values_competitive
    )

    # create the choropleth mapbox
    bigger_markdown(
        "This map shows the percent of vehicle trips in each community region that can competitively shift (maximum bidirectional difference of 15 minutes) to the fastest alternative non-car mode."
    )

    fig3 = px.choropleth_map(
        communities,
        geojson=communities.geometry,
        locations=communities.index,
        color=f"Percent of vehicle trips that can shift {adjective}",
        color_continuous_scale="viridis_r",
        range_color=(0, 1),
        map_style="carto-positron",
        center={"lat": 44.9778, "lon": -93.2650},
        zoom=7.5,
        opacity=0.8,
    )
    fig3.update_layout(
        margin=dict(l=0, r=0, b=0, t=70),
        title=dict(
            text="Percent of vehicle trips in CTUs that can competitively shift to a non-car mode",
            x=0,
            y=0.98,
            yanchor="top",
            xanchor="left",
        ),
        width=900,
        height=500,
    )
    fig3.update_coloraxes(
        colorbar_title_text="Percent of<br>vehicle trips<br>that can<br>competitively<br>shift",
        colorbar_tickformat="0%",
    )
    fig3.update_geos(fitbounds="locations", visible=False)
    fig3.update_traces(
        hovertemplate="<b>%{location}</b><br>Can competitively shift: %{z:.1%}<extra></extra>"
    )
    st.plotly_chart(format_figure(fig3))

    # display various raw metrics regarding shifts/other indicators
    section_header("Raw metrics")

    # person trip count before/after mode shifts
    bigger_markdown(
        inspect.cleandoc(
            f"""- Total number of person trips on car before applying mode shifts: <strong>{round(df[df['mode'] == Mode.CAR]["person_trips"].sum()):,}</strong>
            - Total number of person trips on car after applying mode shifts: <strong>{round(df[(df['mode'] == Mode.CAR) & (~df[f'{st.session_state.phase}_shift'])]["person_trips"].sum()):,}</strong>"""
        )
    )

    st.text("")

    # vehicle trp count before/after mode shifts
    bigger_markdown(
        inspect.cleandoc(
            f"""- Total number of vehicle trips on car before applying mode shifts: <strong>{round(df[df['mode'] == Mode.CAR]['vehicle_trips'].sum()):,}</strong>
            - Total number of vehicle trips on car after applying mode shifts: <strong>{round(df[(df['mode'] == Mode.CAR) & (~df[f'{st.session_state.phase}_shift'])]['vehicle_trips'].sum()):,}</strong>"""
        )
    )

    st.text("")

    # VMT before/after mode shifts
    bigger_markdown(
        inspect.cleandoc(
            f"""- Total VMT before applying {st.session_state.phase} mode shift: <strong>{round(df[df['mode'] == Mode.CAR]['vmt'].sum()):,}</strong>
        - Total VMT after applying {st.session_state.phase} mode shift: <strong>{round(df[(df['mode'] == Mode.CAR) & (~df[f'{st.session_state.phase}_shift'])]['vmt'].sum()):,}</strong>"""
        )
    )

    st.text("")

    # run cold start logic (this takes a bit, hence the spinner) to see cold starts before/after shifts
    with st.spinner("Running cold start logic"):
        before_cold_starts = (
            df[df["mode"] == Mode.CAR]
            .groupby(["wave", "person_id", "travel_date"], group_keys=True)
            .apply(
                lambda x: get_num_cold_starts(
                    list(x["depart_time"]), x["duration"].values, list(x["mode"])
                )
            )
            .sum()
        )
        after_cold_starts = (
            df[(df["mode"] == Mode.CAR) & (~df[f"{st.session_state.phase}_shift"])]
            .groupby(["wave", "person_id", "travel_date"], group_keys=True)
            .apply(
                lambda x: get_num_cold_starts(
                    list(x["depart_time"]), x["duration"].values, list(x["mode"])
                )
            )
            .sum()
        )
        if (~df[f"{st.session_state.phase}_shift"]).sum() == 0:
            after_cold_starts = 0

    # cold shifts before/after mode shifts
    bigger_markdown(
        inspect.cleandoc(
            f"""- Number of cold starts before applying {st.session_state.phase} mode shifts: <strong>{before_cold_starts:,}</strong>
            - Number of cold starts after applying {st.session_state.phase} mode shifts: <strong>{after_cold_starts:,}</strong>"""
        )
    )

    # various bar charts showing the ability to shift across various categories
    section_header("Shifts by categories")
    bar_hovertemplate = "<b>%{x}</b><br>Percent of vehicle trips: %{y:.1%}<br>Total vehicle trips: %{marker.color:,.0f}<extra></extra>"

    # ability to shift when segmented by income bracket
    bigger_markdown(
        r"Below, the % of vehicle trips that can shift when segmented by income bracket is shown."
    )

    # get the % of vehicle trips in each income group that can shift & reorder the columns into a readable order
    income_pct = (
        df.groupby(["income_cleaned", f"{st.session_state.phase}_shift"])[
            ["vehicle_trips"]
        ]
        .sum()
        .reset_index()
    )
    income_pct["percent_vehicle_trips"] = income_pct[
        "vehicle_trips"
    ] / income_pct.groupby("income_cleaned")["vehicle_trips"].transform("sum")
    income_pct = income_pct[income_pct["income_cleaned"] != "na"]

    # creat the barplot
    fig4 = px.bar(
        income_pct[income_pct[f"{st.session_state.phase}_shift"]],
        x="income_cleaned",
        y="percent_vehicle_trips",
        color="vehicle_trips",
        range_color=(0, 2000000),
        range_y=[0, 1.1],
        labels={
            "percent_vehicle_trips": "Percent of vehicle trips",
            "vehicle_trips": "Total vehicle trips",
        },
        category_orders=dict(
            income_cleaned=[
                "Under $25,000",
                "$25,000-$49,999",
                "$50,000-$74,999",
                "$75,000-$99,999",
                "$100,000-$149,999",
                "$150,000 or more",
                "na",
            ]
        ),
    )
    fig4.update_layout(
        title={
            "text": "Percent of vehicle trips that can shift modes by income group",
            "x": 0,
            "xanchor": "left",
            "y": 0.98,
            "yanchor": "top",
        },
        xaxis_title_text="Income group",
        yaxis_title_text=f"Percent of vehicle trips in the<br>category that can {adjective} shift",
        showlegend=False,
    )
    fig4.update_traces(hovertemplate=bar_hovertemplate)
    fig4.update_yaxes(showgrid=True, zeroline=True, tickformat="0%")
    st.plotly_chart(format_figure(fig4))

    # ability to shift by trip purpose (usually destination purpose unless destination is home, then origin purpose -- this is done in the intiialization step)
    bigger_markdown(
        r"Below, the % of vehicle trips that can shift when segmented by trip purpose are shown."
    )

    purpose_pct = (
        df.groupby(["purpose_cleaned", f"{st.session_state.phase}_shift"])[
            ["vehicle_trips"]
        ]
        .sum()
        .reset_index()
    )
    purpose_pct["percent_vehicle_trips"] = purpose_pct[
        "vehicle_trips"
    ] / purpose_pct.groupby("purpose_cleaned")["vehicle_trips"].transform("sum")

    fig5 = px.bar(
        purpose_pct[purpose_pct[f"{st.session_state.phase}_shift"]],
        x="purpose_cleaned",
        y="percent_vehicle_trips",
        color="vehicle_trips",
        range_color=(0, 2000000),
        range_y=[0, 1.1],
        labels={
            "percent_vehicle_trips": "Percent of vehicle trips",
            "vehicle_trips": "Total vehicle trips",
        },
        category_orders=dict(
            purpose_cleaned=[
                "Work",
                "School",
                "Escort",
                "Shop",
                "Errand",
                "Meal",
                "Social/Recreation",
                "Other",
            ]
        ),
    )
    fig5.update_layout(
        title={
            "text": "Percent of vehicle trips that can shift mode by trip purpose",
            "x": 0,
            "xanchor": "left",
            "y": 0.98,
            "yanchor": "top",
        },
        xaxis_title_text="Trip Purpose",
        yaxis_title_text=f"Percent of vehicle trips in the<br>category that can {adjective} shift",
        showlegend=False,
    )
    fig5.update_traces(hovertemplate=bar_hovertemplate)
    fig5.update_yaxes(showgrid=True, zeroline=True, tickformat="0%")
    st.plotly_chart(format_figure(fig5))

    # ability to shift by person type (adult, student, etc.)
    bigger_markdown(
        r"Below, the % of vehicle trips that can shift when segmented by person type are shown."
    )

    person_pct = (
        df.groupby(["person_type", f"{st.session_state.phase}_shift"])[
            ["vehicle_trips"]
        ]
        .sum()
        .reset_index()
    )
    person_pct["percent_vehicle_trips"] = person_pct[
        "vehicle_trips"
    ] / person_pct.groupby("person_type")["vehicle_trips"].transform("sum")

    fig6 = px.bar(
        person_pct[person_pct[f"{st.session_state.phase}_shift"]],
        x="person_type",
        y="percent_vehicle_trips",
        color="vehicle_trips",
        range_color=(0, 3000000),
        range_y=[0, 1.1],
        labels={
            "percent_vehicle_trips": "Percent of vehicle trips",
            "vehicle_trips": "Total vehicle trips",
        },
        category_orders=dict(
            person_type=[
                "Working adult with kids",
                "Working adult without kids",
                "Non-working adult with kids",
                "Non-working adult without kids",
                "Retired",
                "College student",
                "Child",
            ]
        ),
    )
    fig6.update_layout(
        title={
            "text": "Percent of vehicle trips that can shift mode by person type",
            "x": 0,
            "xanchor": "left",
            "y": 0.98,
            "yanchor": "top",
        },
        xaxis_title_text="Person type",
        yaxis_title_text=f"Percent of vehicle trips in the<br>category that can {adjective} shift",
        showlegend=False,
    )
    fig6.update_traces(hovertemplate=bar_hovertemplate)
    fig6.update_yaxes(showgrid=True, zeroline=True, tickformat="0%")
    st.plotly_chart(format_figure(fig6))

    # ability to shift by gender
    bigger_markdown(
        r"Below, the % of trips that can shift when segmented by gender are shown."
    )

    gender_pct = (
        df.groupby(["gender_cleaned", f"{st.session_state.phase}_shift"])[
            ["vehicle_trips"]
        ]
        .sum()
        .reset_index()
    )
    gender_pct["percent_vehicle_trips"] = gender_pct[
        "vehicle_trips"
    ] / gender_pct.groupby("gender_cleaned")["vehicle_trips"].transform("sum")
    gender_pct = gender_pct[
        gender_pct["gender_cleaned"] != "Other/Prefer to self-describe"
    ]

    fig7 = px.bar(
        gender_pct[gender_pct[f"{st.session_state.phase}_shift"]],
        x="gender_cleaned",
        y="percent_vehicle_trips",
        color="vehicle_trips",
        range_color=(0, 5000000),
        range_y=[0, 1.1],
        labels={
            "percent_vehicle_trips": "Percent of vehicle trips",
            "vehicle_trips": "Total vehicle trips",
        },
    )
    fig7.update_layout(
        title={
            "text": "Percent of vehicle trips that can shift mode by gender",
            "x": 0,
            "xanchor": "left",
            "y": 0.98,
            "yanchor": "top",
        },
        xaxis_title_text="Gender",
        yaxis_title_text=f"Percent of vehicle trips in the<br>category that can {adjective} shift",
        showlegend=False,
    )
    fig7.update_traces(hovertemplate=bar_hovertemplate)
    fig7.update_yaxes(showgrid=True, zeroline=True, tickformat="0%")
    st.plotly_chart(format_figure(fig7))

    # ability to shift by recorded TBI wave (either 1/2)
    bigger_markdown(
        r"Below, the % of trips that can shift when segmented by TBI wave is shown."
    )

    wave_pct = (
        df.groupby(["wave", f"{st.session_state.phase}_shift"])[["vehicle_trips"]]
        .sum()
        .reset_index()
    )
    wave_pct["percent_vehicle_trips"] = wave_pct["vehicle_trips"] / wave_pct.groupby(
        "wave"
    )["vehicle_trips"].transform("sum")

    fig8 = px.bar(
        wave_pct[wave_pct[f"{st.session_state.phase}_shift"]],
        x="wave",
        y="percent_vehicle_trips",
        color="vehicle_trips",
        range_color=(0, 5000000),
        range_y=[0, 1.1],
        labels={
            "percent_vehicle_trips": "Percent of vehicle trips",
            "vehicle_trips": "Total vehicle trips",
        },
    )
    fig8.update_layout(
        title={
            "text": "Percent of vehicle trips that can shift mode by TBI wave",
            "x": 0,
            "xanchor": "left",
            "y": 0.98,
            "yanchor": "top",
        },
        xaxis_title_text="Wave",
        yaxis_title_text=f"Percent of vehicle trips in the<br>category that can {adjective} shift",
        showlegend=False,
    )
    fig8.update_traces(hovertemplate=bar_hovertemplate)
    fig8.update_yaxes(showgrid=True, zeroline=True, tickformat="0%")
    st.plotly_chart(format_figure(fig8))

    # various metrics for tour-level shifts that are possible
    section_header("Tour-level shifts")

    # a tour can shift to a mode if and only if all component trips can shift to that mode
    temp = pd.merge(
        left=df[["wave", "person_id", "travel_date"]],
        right=df.groupby(["wave", "person_id", "travel_date"]).agg(
            {
                f"{st.session_state.phase}_walk_shift": "all",
                f"{st.session_state.phase}_bike_shift": "all",
                f"{st.session_state.phase}_transit_shift": "all",
            }
        ),
        left_on=["wave", "person_id", "travel_date"],
        right_index=True,
        how="left",
    )
    # a little fanagling to change df in-place
    df[f"{st.session_state.phase}_walk_shift_tour"] = temp[
        f"{st.session_state.phase}_walk_shift"
    ]
    df[f"{st.session_state.phase}_bike_shift_tour"] = temp[
        f"{st.session_state.phase}_bike_shift"
    ]
    df[f"{st.session_state.phase}_transit_shift_tour"] = temp[
        f"{st.session_state.phase}_transit_shift"
    ]

    # a tour can shift if it can shift to any individual mode
    df[f"{st.session_state.phase}_shift_tour"] = (
        df[f"{st.session_state.phase}_walk_shift_tour"]
        | df[f"{st.session_state.phase}_bike_shift_tour"]
        | df[f"{st.session_state.phase}_transit_shift_tour"]
    )

    # create a dataframe to show the % of car trips/vmt that can be mitigated when considering only tour-level shifts as possible and display this in streamlit
    tour_df = pd.DataFrame(index=[r"% of Car Trips", r"% of VMT"])
    tour_df["Feasible to switch to walk"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_walk_shift_tour"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_walk_shift_tour"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    tour_df["Feasible to switch to bike"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_bike_shift_tour"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_bike_shift_tour"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    tour_df["Feasible to switch to transit"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_transit_shift_tour"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_transit_shift_tour"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]
    tour_df["Feasible to switch to any non-car mode"] = [
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift_tour"])]["vehicle_trips"].sum() / df[(df["mode"] == Mode.CAR)]["vehicle_trips"].sum() * 100:.1f}%',
        f'{df[(df["mode"] == Mode.CAR) & (df[f"{st.session_state.phase}_shift_tour"])]["vmt"].sum() / df[(df["mode"] == Mode.CAR)]["vmt"].sum() * 100:.1f}%',
    ]

    bigger_markdown(
        f"We consider a tour-level shift possible if every component trip can also shift {adjective}."
    )
    st.table(register_summary_table("tour_df", tour_df))


def show_step() -> None:
    """
    This function generates the step we are currently at, including all information blurbs/interactiveness.
    """

    # get an alias to the current step for easy reference later
    curr: steps.parent_classes.BaseStep = st.session_state["step_class"]
    # title the page by the step name
    st.title(f"{curr.get_name()}{city_title_suffix()}")

    # if the step we are at is continuous, have settings for setting the cutoff/choosing between pct/raw selection/a blurb for the equivalent opposite cutoff
    if curr.is_continuous():
        curr.set_cutoff_mode(
            st.sidebar.radio(
                "Choose how to set the cutoff",
                (CutoffMode.PCT, CutoffMode.RAW),
                index=1 if curr.get_cutoff_mode() == CutoffMode.RAW else 0,
                key=st.session_state.id,
            )
        )
        if curr.get_cutoff_mode() == CutoffMode.PCT:
            curr.set_cutoff(
                st.sidebar.slider(
                    "Select a value:",
                    0.0,
                    1.0,
                    0.95,
                    0.01,
                    format="%.2f",
                    key=st.session_state.id + 1,
                )
            )
            st.sidebar.markdown(
                f"Cutoff equivalent: {curr.get_cutoff_equivalent():.1f} {curr.get_units()}"
            )
        elif curr.get_cutoff_mode() == CutoffMode.RAW:
            extrema = curr.get_extrema()
            raw_cutoff = st.session_state.get("default_raw_cutoffs", {}).get(
                st.session_state.step, float(extrema[1])
            )
            min_value = min(float(extrema[0]), float(raw_cutoff))
            max_value = max(float(extrema[1]), float(raw_cutoff))
            curr.set_cutoff(
                st.sidebar.number_input(
                    f"Select a value ({curr.get_units()}):",
                    min_value=min_value,
                    max_value=max_value,
                    value=float(raw_cutoff),
                    step=float((extrema[1] - extrema[0]) / 100),
                    format="%0.2f",
                    key=st.session_state.id + 2,
                )
            )
            st.sidebar.markdown(
                f"Cutoff equivalent: {curr.get_cutoff_equivalent() * 100:.2f}th percentile"
            )
        else:
            logging.exception(
                "Something went worng with the cutoff mode enum: %s",
                curr.get_cutoff_mode(),
            )
            raise RuntimeError("something went wrong")

    # button to dsiable the current step
    if st.sidebar.button("Skip (disable) this step", use_container_width=True):
        curr.disable()

    # button to apply (& show the entire narrative of the current step); otherwise, just have a blurb on the current step/how to run it
    if st.sidebar.button("Apply cutoff and show results", use_container_width=True):
        curr.apply_step()
        curr.show_step_streamlit()
    else:
        st.header(
            "Click Apply cutoff and show results once the desired settings have been set, or Skip (disable) this step to leave it out."
        )
        bigger_markdown(curr.get_desc())


def switch_to_step(step: str) -> None:
    """
    This function makes the given step the current one, creating a fresh instance of it (the step being left keeps its settings).
    """
    logging.info("Moving to new step %s from step %s", step, st.session_state.step)
    st.session_state.step = step
    st.session_state.step_class_dict[step] = initialize_step(step)
    st.session_state.step_class = st.session_state.step_class_dict[step]
    # new widget keys so the cutoff controls reset for the new step
    st.session_state.id += 10


def run() -> None:
    """
    This function provides the main wrapper for the visualization tool, implementing actions like switching between steps/moving to sumary
    """

    # define possible actions
    st.sidebar.header("Actions")

    if st.session_state.phase == Phase.FEASIBLE:
        step_names = st.session_state["feasible_steps"]
    elif st.session_state.phase == Phase.PROBABLE:
        step_names = st.session_state["probable_steps"]
    else:
        logging.exception(
            "something went wrong with the overall step session state variable: %s",
            st.session_state.phase,
        )
        raise RuntimeError(
            "Something went wrong with the overall step session state variable"
        )

    # can only go to new steps; TODO: add functionality to save snapshots after each step is left to allow full backtracking
    options = [
        step
        for step in step_names
        if step not in st.session_state.step_class_dict
        or step == st.session_state.step
        or st.session_state.step_class_dict[step].get_previous_run() is None
    ]
    current_index = step_names.index(st.session_state.step)
    next_step = next(
        (step for step in step_names[current_index + 1 :] if step in options), None
    )

    if next_step is not None and st.sidebar.button(
        f"Next step: {next_step}", type="primary"
    ):
        switch_to_step(next_step)
        st.rerun()

    # finish and move to summary button -- toggle summary screen to true & refresh
    if st.sidebar.button("Finish phase and view summary"):
        logging.info("Moving to the summary step")
        st.session_state.summary_screen = True
        st.rerun()

    option = st.sidebar.selectbox(
        "Choose the step you want to run. If you move away from the current step, the settings of the current step will be 'locked in' and will be unable to be changed.",
        options,
        index=options.index(st.session_state.step),
        # id changes on every step switch, so the box resets to the new current step
        key=f"step_select_{st.session_state.id}",
    )

    # manual refresh of the tool -- may break the tool
    if st.sidebar.button("Refresh page"):
        logging.info("Refreshing the tool")
        st.rerun()

    if st.session_state.step != option:
        switch_to_step(option)

    # show the meat of the current step
    show_step()

    # create a dropdown showing the steps that have already been run & their associated cutoffs
    d = {}

    # iterate over all steps in the dictionary
    for name, step in st.session_state.step_class_dict.items():
        # if the step has a previous run, means it has been ran and only process it if this is true
        if step.get_previous_run() != None:
            prev = step.get_previous_run()

            # if continuous, show with percentile/units as necessary
            if step.is_continuous():
                if prev[1] == CutoffMode.PCT:
                    d[name] = (
                        f"{prev[0] * 100:.0f}th pct ({step.get_pct_value(prev[0]):.1f} {step.get_units()})"
                    )
                elif prev[1] == CutoffMode.RAW:
                    d[name] = f"{prev[0]:.1f} {step.get_units()}"
                else:
                    logging.exception(
                        "Something went wrong with the cutoff mode enum: %s", prev[1]
                    )
                    raise RuntimeError("Something went wrong with the cutoff mode enum")
            # otherwise, just show 1
            else:
                d[name] = "1 (categorical)"

    with st.sidebar.expander("See previously run steps"):
        st.write(d)

    # blurb about exporting to PDF from webpage
    st.sidebar.markdown(
        "To export this page to PDF, click the x button above to dismiss the sidebar, and then manually print to PDF"
    )


# main serving function of strealit application
if __name__ == "__main__":
    # hacky function to allow for bigger font sizes
    st.markdown(
        """
            <style>
                .bigger-font {
                    font-size: 1.2rem !important;
                }
                [data-testid="stMainBlockContainer"] {
                    max-width: 1000px;
                }
                .toc {
                    position: fixed;
                    top: 5rem;
                    right: 1.5rem;
                    width: 14rem;
                    display: flex;
                    flex-direction: column;
                    gap: 0.25rem;
                    font-size: 0.9rem;
                    z-index: 100;
                }
                .toc a {
                    text-decoration: none;
                }
                .toc .toc-phase {
                    font-weight: 600;
                    margin-top: 0.5rem;
                }
                .toc .toc-section {
                    padding-left: 0.75rem;
                }
                /* no room beside the 1000px main column on narrow screens */
                @media (max-width: 1400px) {
                    .toc {
                        display: none;
                    }
                }
            </style>
        """,
        unsafe_allow_html=True,
    )

    scenario = select_scenario()

    # do initiali variable setup; this only runs on first startup
    # this forces the tool to start at start screen feasible
    if "start_screen_feasible" not in st.session_state:
        logging.info("Doing initial setup")
        st.session_state["start_screen_feasible"] = True
        st.session_state["start_screen_probable"] = False
        st.session_state.id = 0

    # main page handler -- in general, if any session state page indicator is True, run that and only one indicator should be True at a time

    # initial setup again -- setup df
    if "df" not in st.session_state:
        with st.spinner("Setting up application"):
            setup_df()
        st.rerun()
    # run the start screen for the feasible phase
    elif st.session_state.start_screen_feasible:
        start_screen_feasible()
    # run the start screen for the probable phase
    elif st.session_state.start_screen_probable:
        start_screen_probable()
    # run the summary screen
    elif st.session_state.summary_screen:
        final_summary()
    # default -- only runs with no indicators -- shows the current step/wrapper for the tool
    else:
        run()
