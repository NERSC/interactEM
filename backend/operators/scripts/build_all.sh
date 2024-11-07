#!/bin/bash

set -e

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Define the operators directory relative to this script
OPERATORS_DIR="$SCRIPT_DIR/../../operators"

BACKEND_DIR="$SCRIPT_DIR/../../"

# Define the containerfiles directory
CONTAINERFILES_DIR="$OPERATORS_DIR/containerfiles"

# Initialize an array to hold process IDs (PIDs) of background jobs
declare -a pids

# Counter for PIDs array
i=0

# Loop over each directory in the containerfiles directory
for dir in "$CONTAINERFILES_DIR"/*; do
    if [ -d "$dir" ]; then
        op_name=$(basename "$dir")
        containerfile="$dir/Containerfile"
        if [ -f "$containerfile" ]; then
            echo "Found Containerfile for $op_name"

            echo "Building image for $op_name"
            # Start the build in background and collect its PID
            podman build -t "interactem/$op_name" "$BACKEND_DIR" -f $containerfile &
            pids[$i]=$!
            ((i++))
        else
            echo "No Containerfile in $dir, skipping"
        fi
    fi
done

# Wait for all background builds to complete
for pid in "${pids[@]}"; do
    wait "$pid"
done

echo "All builds completed"