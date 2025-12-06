#!/usr/bin/env bash

# Use python3 to be explicit. When a venv is active, this will correctly
# point to the interpreter inside the venv.
python3 ./src/main.py "$@"
