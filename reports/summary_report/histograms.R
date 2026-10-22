library(plotly)
library(dplyr)

load_histogram_trips <- function(summary_output_dir) {
    trips_path <- file.path(summary_output_dir, "trips_base.parquet")

    if (!file.exists(trips_path)) {
        stop("Trip export not found: ", trips_path, call. = FALSE)
    }

    arrow::read_parquet(trips_path)
}

stacked_shift_histogram <- function(trips,
                                    mode,
                                    mode_duration,
                                    mode_feasible_field,
                                    phase = "feasible") {
    mode_label <- paste0(toupper(substr(mode, 1, 1)), substring(mode, 2))
    mode_trips <- paste(mode_label, "Trips")
    feasible_trips <- paste("Drive Trips -", phase, "to Switch")
    infeasible_trips <- paste("Drive Trips - Not", phase, "to Switch")

    if (mode == "transit") {
        trips <- trips %>%
            dplyr::filter(
                !is.na(.data$transit_duration),
                .data$transit_duration > 0,
                .data$transit_duration < 1440
            )
    }

    histogram_data <- trips %>%
        dplyr::mutate(
            duration_difference = .data[[mode_duration]] - .data$car_duration_seconds_adj / 60,
            category = dplyr::case_when(
                .data$mode == .env$mode ~ .env$mode_trips,
                .data$mode == "car" & .data[[mode_feasible_field]] ~ .env$feasible_trips,
                .data$mode == "car" & !.data[[mode_feasible_field]] ~ .env$infeasible_trips,
                TRUE ~ NA_character_
            ),
            category = factor(
                .data$category,
                levels = c(.env$infeasible_trips, .env$feasible_trips, .env$mode_trips)
            )
        ) %>%
        dplyr::filter(
            !is.na(.data$category),
            !is.na(.data$duration_difference),
            .data$duration_difference >= -15,
            .data$duration_difference < 150
        ) %>%
        dplyr::mutate(
            bin_start = floor(.data$duration_difference + 15) - 15,
            bin_center = .data$bin_start + 0.5
        ) %>%
        dplyr::group_by(.data$category, .data$bin_start, .data$bin_center) %>%
        dplyr::summarise(
            person_trips = sum(.data$person_trips, na.rm = TRUE),
            .groups = "drop"
        ) %>%
        dplyr::mutate(bin_end = .data$bin_start + 1)

    category_colors <- c(
        infeasible_trips = "#0068C9",
        feasible_trips = "#83C9FF",
        mode_trips = "#FF2B2B"
    )
    names(category_colors) <- c(infeasible_trips, feasible_trips, mode_trips)

    histogram_plot <- purrr::reduce(
        names(category_colors),
        function(plot, category_name) {
            category_data <- histogram_data %>%
                dplyr::filter(as.character(.data$category) == .env$category_name)

            if (nrow(category_data) == 0) {
                return(plot)
            }

            plotly::add_trace(
                plot,
                data = category_data,
                x = ~bin_center,
                y = ~person_trips,
                type = "bar",
                name = category_name,
                width = 1,
                text = paste0(
                    category_data$bin_start,
                    " - ",
                    category_data$bin_end,
                    " min"
                ),
                textposition = "none",
                marker = list(color = category_colors[[category_name]]),
                hovertemplate = paste0(
                    "<b>%{fullData.name}</b><br>Time difference: %{text}",
                    "<br>Person trips: %{y:,.0f}<extra></extra>"
                )
            )
        },
        .init = plotly::plot_ly()
    )

    histogram_plot %>%
        councilR::plotly_layout(
            main_title = paste(
                "Stacked histogram of duration difference between equivalent",
                mode,
                "and driving trips"
            ),
            x_title = paste0("Travel Time Difference (", mode, " - drive time, minutes)"),
            y_title = "Person Trips"
        ) %>%
        plotly::layout(
            barmode = "stack",
            bargap = 0,
            legend = list(
                x = 0.99,
                y = 0.99,
                xref = "paper",
                yref = "paper",
                xanchor = "right",
                yanchor = "top"
            ),
            xaxis = list(
                range = c(-15, 150)
            ),
            yaxis = list(type = "linear", rangemode = "tozero"),
            shapes = list(list(
                type = "line",
                xref = "x",
                yref = "paper",
                x0 = 15,
                x1 = 15,
                y0 = 0,
                y1 = 1,
                line = list(color = "black", dash = "dash")
            )),
            annotations = list(list(
                x = 15,
                y = 1,
                xref = "x",
                yref = "paper",
                text = "15 min",
                font = list(family = "Arial Narrow", size = 20),
                showarrow = FALSE,
                xanchor = "left",
                yanchor = "bottom"
            ))
        )
}

total_shift_histogram <- function(trips, phase = "feasible") {
    infeasible_trips <- paste("Drive trips - not", phase, "to switch")
    walk_shift_field <- paste0(phase, "_walk_shift")
    bike_shift_field <- paste0(phase, "_bike_shift")
    transit_shift_field <- paste0(phase, "_transit_shift")
    # browser()
    histogram_data <- trips %>%
        dplyr::mutate(
            feasible_walk_duration = dplyr::if_else(
                .data[[walk_shift_field]], .data$walk_duration_seconds, 9999999
            ),
            feasible_bike_duration = dplyr::if_else(
                .data[[bike_shift_field]], .data$bike_duration_seconds_adj, 9999999
            ),
            feasible_transit_duration = dplyr::if_else(
                .data[[transit_shift_field]], .data$transit_duration_seconds_na, 9999999
            ),
            min_feasible_alt_mode_duration = pmin(
                .data$feasible_walk_duration,
                .data$feasible_bike_duration,
                .data$feasible_transit_duration,
                na.rm = TRUE
            ),
            fastest_phase_mode = dplyr::case_when(
                .data[[transit_shift_field]] &
                    .data$transit_duration_seconds_na == .data$min_feasible_alt_mode_duration ~ "transit",
                .data[[bike_shift_field]] &
                    .data$bike_duration_seconds_adj == .data$min_feasible_alt_mode_duration ~ "bike",
                .data[[walk_shift_field]] &
                    .data$walk_duration_seconds == .data$min_feasible_alt_mode_duration ~ "walk",
                TRUE ~ "na"
            ),
            min_alt_mode_duration = pmin(
                .data$walk_duration_seconds,
                .data$bike_duration_seconds_adj,
                .data$transit_duration_seconds_na,
                na.rm = TRUE
            ),
            min_alt_mode_duration = dplyr::if_else(
                .data$fastest_phase_mode == "na",
                .data$min_alt_mode_duration,
                .data$min_feasible_alt_mode_duration
            ),
            duration_difference = (
                .data$min_alt_mode_duration - .data$car_duration_seconds_adj
            ) / 60,
            category = dplyr::case_when(
                # .data$mode %in% c("car", "Taxi/Ridehail/Carshare") &
                .data$fastest_phase_mode == "walk" ~ "Walk is fastest alternative",
                # .data$mode %in% c("car", "Taxi/Ridehail/Carshare") &
                .data$fastest_phase_mode == "bike" ~ "Bike is fastest alternative",
                # .data$mode %in% c("car", "Taxi/Ridehail/Carshare") &
                .data$fastest_phase_mode == "transit" ~ "Transit is fastest alternative",
                # .data$mode %in% c("car", "Taxi/Ridehail/Carshare") &
                .data$fastest_phase_mode == "na" ~ .env$infeasible_trips,
                TRUE ~ NA_character_
            ),
            category = factor(
                .data$category,
                levels = c(
                    .env$infeasible_trips,
                    "Walk is fastest alternative",
                    "Bike is fastest alternative",
                    "Transit is fastest alternative"
                )
            )
        ) %>%
        dplyr::filter(
            !is.na(.data$category),
            !is.na(.data$duration_difference),
            .data$duration_difference >= -15,
            .data$duration_difference < 150
        ) %>%
        dplyr::mutate(
            bin_start = floor(.data$duration_difference + 15) - 15,
            bin_center = .data$bin_start + 0.5
        ) %>%
        dplyr::group_by(.data$category, .data$bin_start, .data$bin_center) %>%
        dplyr::summarise(
            vehicle_trips = sum(.data$vehicle_trips, na.rm = TRUE),
            .groups = "drop"
        ) %>%
        dplyr::mutate(bin_end = .data$bin_start + 1)

    category_colors <- c(
        infeasible_trips = "#0068C9",
        "Walk is fastest alternative" = "#7F7F7F",
        "Bike is fastest alternative" = "#BCBD22",
        "Transit is fastest alternative" = "#17BECF"
    )
    names(category_colors)[1] <- infeasible_trips

    histogram_plot <- purrr::reduce(
        names(category_colors),
        function(plot, category_name) {
            category_data <- histogram_data %>%
                dplyr::filter(as.character(.data$category) == .env$category_name)

            if (nrow(category_data) == 0) {
                return(plot)
            }

            plotly::add_trace(
                plot,
                data = category_data,
                x = ~bin_center,
                y = ~vehicle_trips,
                type = "bar",
                name = category_name,
                text = paste0(
                    category_data$bin_start,
                    " - ",
                    category_data$bin_end,
                    " min"
                ),
                textposition = "none",
                width = 1,
                marker = list(color = category_colors[[category_name]]),
                hovertemplate = paste0(
                    "<b>%{fullData.name}</b><br>Time difference: %{text}",
                    "<br>Vehicle trips: %{y:,.0f}<extra></extra>"
                )
            )
        },
        .init = plotly::plot_ly(height = 500)
    )

    histogram_plot %>%
        councilR::plotly_layout(
            main_title = paste(
                "Stacked histogram of duration difference between fastest feasible",
                "alternative and driving"
            ),
            x_title = "Travel Time Difference (alternative - drive time, minutes)",
            y_title = "Vehicle Trips"
        ) %>%
        plotly::layout(
            barmode = "stack",
            bargap = 0,
            xaxis = list(
                range = c(-15, 150)
            ),
            legend = list(
                x = 0.99,
                y = 0.99,
                xref = "paper",
                yref = "paper",
                xanchor = "right",
                yanchor = "top"
            ),
            yaxis = list(type = "linear", rangemode = "tozero"),
            shapes = list(list(
                type = "line",
                xref = "x",
                yref = "paper",
                x0 = 15,
                x1 = 15,
                y0 = 0,
                y1 = 1,
                line = list(color = "black", dash = "dash")
            )),
            annotations = list(list(
                x = 15,
                y = 1,
                xref = "x",
                yref = "paper",
                text = "15 min",
                font = list(family = "Arial Narrow", size = 20),
                showarrow = FALSE,
                xanchor = "left",
                yanchor = "bottom"
            ))
        )
}
