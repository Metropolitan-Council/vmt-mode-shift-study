#!/usr/bin/env bash

source /venv/bin/activate
streamlit run /app/main.py --server.port=8501 --server.address=0.0.0.0