library(councilR)
library(dplyr)
library(purrr)
library(tidyr)

suppressMessages(here::i_am("reports/summary_report/compile_streamlit_ouput.R"))
summary_output_dir <- get0(
    "summary_output_dir",
    ifnotfound = here::here("src", "analysis_tool", "output"),
    inherits = TRUE
)
summary_options <- jsonlite::fromJSON(file.path(summary_output_dir, "options_base.json"))
feasible_options <- summary_options$feasible
walk_distance_cutoff <- feasible_options$WalkDistanceStep$cutoff
bike_distance_cutoff <- feasible_options$BikeDistanceStep$cutoff
bike_high_lts_distance_cutoff <- feasible_options$BikeHighLTSDistStep$cutoff
bike_snow_depth_cutoff <- feasible_options$BikeSnowDepthStep$cutoff
transit_access_distance_cutoff <- feasible_options$TransitAccessDistanceStep$cutoff
transit_egress_distance_cutoff <- feasible_options$TransitEgressDistanceStep$cutoff
transit_wait_time_cutoff <- feasible_options$TransitWaitTimeStep$cutoff

# create labels -----
walk_distance_label <- paste0(
    "Walking distance < ",
    format(walk_distance_cutoff, trim = TRUE, scientific = FALSE),
    " miles"
)
bike_distance_label <- paste0(
    "Biking distance < ",
    format(bike_distance_cutoff, trim = TRUE, scientific = FALSE),
    " miles"
)
bike_high_lts_cutoff_label <- sub(
    "\\.0%$",
    "%",
    scales::percent(bike_high_lts_distance_cutoff, accuracy = 0.1)
)
bike_high_lts_distance_label <- paste0(
    "No more than ",
    bike_high_lts_cutoff_label,
    " of the distance is on LTS 3 or 4 facilities"
)
transit_access_label <- paste0(
    "Walk access distance < ",
    format(transit_access_distance_cutoff, trim = TRUE, scientific = FALSE),
    " miles"
)
transit_egress_label <- paste0(
    "Walk egress distance < ",
    format(transit_egress_distance_cutoff, trim = TRUE, scientific = FALSE),
    " miles"
)
transit_wait_label <- paste0(
    "Waiting time for first vehicle is < ",
    format(transit_wait_time_cutoff, trim = TRUE, scientific = FALSE),
    " minutes"
)
summary_files <- list.files(
    summary_output_dir,
    pattern = "^tables_.*\\.json$",
    full.names = TRUE
)

summary_exports <- map(summary_files, jsonlite::fromJSON)
scenario_names <- map_chr(summary_exports, "scenario")


scenario_order <- c("base", sort(setdiff(scenario_names, "base")))

read_summary_table <- function(summary_table) {
    as_tibble(summary_table$data, .name_repair = "minimal") %>%
        set_names(summary_table$columns) %>%
        mutate(row_label = summary_table$index) %>%
        pivot_longer(
            cols = -row_label,
            names_to = "column_label",
            values_to = "value_text",
            values_transform = list(value_text = as.character)
        )
}

summary_cells <- summary_exports %>%
    map(function(summary_export) {
        summary_export$phases %>%
            imap(function(phase_tables, phase_name) {
                phase_tables %>%
                    imap(function(summary_table, table_name) {
                        read_summary_table(summary_table) %>%
                            mutate(
                                scenario = summary_export$scenario,
                                phase = phase_name,
                                table = table_name,
                                .before = 1
                            )
                    }) %>%
                    list_rbind()
            }) %>%
            list_rbind()
    }) %>%
    list_rbind() %>%
    mutate(
        scenario = factor(scenario, levels = scenario_order),
        phase = factor(phase, levels = c("feasible", "probable")),
        column_label = recode_values(
            column_label,
            "Feasible Walking Distance" ~ walk_distance_label,
            "Feasible Walk Timing" ~ "Sufficient time is available to complete the trip",
            "Feasible Bike Timing" ~ "Sufficient time is available to complete the trip",
            "Feasible Transit Timing" ~ "Sufficient time is available to complete the trip",
            "Feasible Bike Snow Depth" ~ "There is not snow on the ground",
            "Feasible Bike High Lts Distance" ~ bike_high_lts_distance_label,
            "Feasible Biking Distance" ~ bike_distance_label,
            "feasible Across All Criteria" ~ "Feasible across all constraints",
            "Feasible Transit Access Distance" ~ transit_access_label,
            "Feasible Transit Egress Distance" ~ transit_egress_label,
            "Feasible Transit Route Found" ~ "Valid transit path found with 2 or fewer transfers",
            "Feasible Transit Timing" ~ "Sufficient time is available to complete the trip",
            "Feasible Transit Wait Time" ~ transit_wait_label,
            default = column_label
        ),
        mode = stringr::str_extract(stringr::str_to_title(column_label), "Walk|Bike|Transit|Any Non-Car Mode") %>% stringr::str_to_sentence(),
        minutes = stringr::str_extract(column_label, "5 minutes|15 minutes|30 minutes")
    )

percentage_cells <- summary_cells %>%
    filter(table != "step_settings") %>%
    mutate(value_pct = readr::parse_number(
        value_text,
        na = c("", "NA", "NaN", "nan", "NaN%", "nan%")
    ) / 100)

base_percentages <- percentage_cells %>%
    filter(scenario == "base") %>%
    select(phase, table, row_label, column_label, base_pct = value_pct)

comparison_long <- percentage_cells %>%
    # left_join(
    #     base_percentages,
    #     by = join_by(phase, table, row_label, column_label),
    #     relationship = "many-to-one"
    # ) %>%
    # mutate(difference_pp = value_pct - base_pct) %>%
    arrange(phase, table, row_label, column_label, scenario)

comparison_wide <- comparison_long %>%
    select(
        phase, table, mode, minutes, row_label, column_label, scenario, value_pct
    ) %>%
    pivot_wider(
        names_from = scenario,
        values_from = c(value_pct),
        names_glue = "{scenario}_{.value}",
        names_vary = "slowest",
        names_expand = TRUE
    )

# make feasibility tables
feas_walk_tables <- comparison_long %>%
    filter(
        phase == "feasible", scenario == "base",
        table %in% c("walk_step_summary", "walk_duration_summary")
    ) %>%
    arrange(column_label)

feas_bike_tables <- comparison_long %>%
    filter(
        phase == "feasible", scenario == "base",
        table %in% c("bike_step_summary", "bike_duration_summary")
    ) %>%
    arrange(column_label)

feas_transit_tables <- comparison_long %>%
    filter(
        phase == "feasible", scenario == "base",
        table %in% c("transit_step_summary", "transit_duration_summary")
    ) %>%
    arrange(column_label)

feas_all_four_tables <- comparison_long %>%
    filter(
        phase == "feasible", scenario == "base",
        table %in% c("overall_shifts", "duration_diff_df", "overall_shift_comparison")
    ) %>%
    arrange(column_label)

# pull scenario tables----

scen_walk <- comparison_long %>%
    filter(
        scenario %in% c("best_walk", "base"),
        phase == "feasible",
        table %in% c("walk_duration_summary")
    ) %>%
    arrange(table, column_label)

scen_bike <- comparison_long %>%
    filter(
        scenario %in% c("best_bike", "base"),
        phase == "feasible",
        table %in% c("bike_duration_summary")
    ) %>%
    arrange(table, column_label)

scen_ebike <- comparison_long %>%
    filter(
        scenario %in% c("e_bike", "base"),
        phase == "feasible",
        table %in% c("bike_duration_summary")
    ) %>%
    arrange(table, column_label)

scen_transit <- comparison_long %>%
    filter(
        scenario %in% c("double_transit", "base"),
        phase == "feasible",
        table %in% c("transit_duration_summary")
    ) %>%
    arrange(table, column_label)

scen_speed <- comparison_long %>%
    filter(
        scenario %in% c("slow_car", "base"),
        phase == "feasible",
        table %in% c("duration_diff_df")
    ) %>%
    arrange(table, column_label)


scen_all_four <- comparison_long %>%
    filter(
        scenario %in% c("base", "all_four"),
        phase == "feasible",
        table %in% c("duration_diff_df")
    ) %>%
    arrange(table, column_label)

compare_all_four <- comparison_long %>%
    filter(
        phase == "feasible",
        table == "duration_diff_df",
        minutes == "15 minutes"
    )


plotting_tables <- list(
    existing = list(
        walk = feas_walk_tables,
        bike = feas_bike_tables,
        transit = feas_transit_tables,
        all_four = feas_all_four_tables
    ),
    potential = list(
        best_walk = scen_walk,
        best_bike = scen_bike,
        e_bike = scen_ebike,
        double_transit = scen_transit,
        slow_car = scen_speed,
        all_four = scen_all_four
    ),
    compare_all_four = compare_all_four
)
