#!/bin/bash

# Run the inventory import script first
python import_inventory.py

# Start the Streamlit app
streamlit run app.py --server.port=8501 --server.address=0.0.0.0