#!/bin/bash
# Automatically run the inventory setup script on startup
python import_inventory.py

# Hand off control to the main application command
exec "$@"