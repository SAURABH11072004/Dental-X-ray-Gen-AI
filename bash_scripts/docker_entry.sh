#!/bin/bash

# Console entry script for docker container

# Run jupyter notebook
jupyter lab --notebook-dir=/app/notebooks --ip=0.0.0.0 --allow-root --port=8888