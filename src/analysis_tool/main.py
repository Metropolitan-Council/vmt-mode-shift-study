import streamlit as st
import pandas as pd

import steps
from initialize import prepare_csv
from settings import handler

if "df" not in st.session_state:
    if handler["force_reinitialize"]:
        with st.spinner(text="Building the input data"):
            raw = pd.read_csv(handler["drive_data_dir"] + "/data_processed/tbi_cleaned.csv")

            df = prepare_csv(raw, handler["drive_data_dir"])
    else:
        try:
            df = pd.read_csv("data/" + handler["tbi_file_name"])
            
        except Exception as e:
            with st.spinner(text="Building the input data"):
                
                raw = pd.read_csv(handler["drive_data_dir"] + "/data_processed/tbi_cleaned.csv")

                df = prepare_csv(raw, handler["drive_data_dir"])
    
    st.session_state["df"] = df
    st.session_state["step"] = "WalkDistanceStep"
    st.session_state["overall_step"] = steps.feasible_steps
    st.session_state["step_class"] = steps.feasible_steps.WalkDistanceStep(df)
    st.session_state["percentiles"] = dict()
    
def show_step():
    curr = st.session_state["step_class"]
    st.title(curr.get_name())
    
    if curr.is_continuous():
        value = st.sidebar.slider("Select a value:", 0.0, 1.0, 0.95, 0.01)
        curr.set_cutoff(value)
        st.sidebar.markdown(f"Cutoff: {curr.get_cutoff_numerical()}")
    
    if st.sidebar.button("Disable step"):
        curr.disable()
    else:
        curr.apply_step()
        
    st.sidebar.markdown("To export this page to PDF, click the x button above to dismiss the sidebar, and then manually print to PDF")
        
    text = curr.get_text()
    
    st.markdown(text[0])
    st.text("")
    
    slots = []
    
    for section in text[1:]:
        st.markdown(section)
        temp = st.empty()
        slots.append(temp)
        
    slots[0].pyplot(curr.get_summary_figure()[0])
    slots[1].dataframe(curr.get_summary_statistics())
    slots[2].plotly_chart(curr.get_map())
    
def SequentialMode():
    if st.sidebar.button("Move to next mode"):
        curr = handler["feasible_steps"].index(st.session_state.step)
        if curr == len(handler["feasible_steps"]):
            st.experimental_rerun()
            pass
        else:
            st.session_state.percentiles[st.session_state.step_class.get_name()] = st.session_state.step_class.get_cutoff()
            st.session_state.step = handler["feasible_steps"][curr + 1]
            st.session_state.step_class = getattr(st.session_state.overall_step, st.session_state.step)(st.session_state.df)        
        
    show_step()

def FreeformMode():
    option = st.sidebar.selectbox("Choose the step you want to run.", handler["feasible_steps"])
    if st.sidebar.button("Finish and move to summary"):
        pass
        
    if st.session_state.step != option:
        st.session_state.percentiles[st.session_state.step_class.get_name()] = st.session_state.step_class.get_cutoff()
        st.session_state.step = option
        st.session_state.step_class = getattr(st.session_state.overall_step, option)(st.session_state.df)
        
    show_step()
    

if __name__ == "__main__":
    st.sidebar.header("Actions")
    FreeformMode()
    # if "settings" not in st.session_state:
    #     mode = st.radio("Choose the mode for the tool", ("Sequential", "Freeform"))
    #     if st.button("Start tool"):
    #         st.session_state["settings"] = True
    #         st.session_state["mode"] = mode
    #         st.experimental_rerun()
            
    # else:
    #     st.sidebar.header("Actions")
    #     if st.session_state.mode == "Sequential":
    #         SequentialMode()
    #     elif st.session_state.mode == "Freeform":
    #         FreeformMode()
    #     else:
    #         raise RuntimeError("Invalid mode passed -- shouldn't be possible")

    