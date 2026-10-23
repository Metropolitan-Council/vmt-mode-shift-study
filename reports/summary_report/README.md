# Summary Report

The summary report consolidates the findings from the feasibility and probability analyses and uses saved outputs from the streamlit app to generate a report following the same structure as [VMT Reduction Mode Shift Final Report.pdf](VMT Reduction Mode Shift Final Report.pdf). 

To render, run the following code from the terminal.

```bash
quarto render summary_report.qmd
```

Relevant files
- summary_report.qmd: The main Quarto file for generating the summary report.
- histograms.R: R script for generating histograms used in the summary report.
- compile_streamlit_output.R: R script for compiling the output from the streamlit app used in the summary report.

You can customize which summary output data is used by modifying the `summary_output_dir` variable in the `summary_report.qmd` file.

```r
summary_output_dir <- here::here("src", "analysis_tool", "output", "Minneapolis")
```