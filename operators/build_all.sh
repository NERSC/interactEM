#!/bin/bash

set -e

# Get the directory of this script
SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(git rev-parse --show-toplevel)

# Build base containers
$ROOT_DIR/docker/build.sh
if [ $? -ne 0 ]; then
    echo "Failed to build base containers."
    exit 1
fi

build_dirs=(
    "background-subtract"
    "data-replay"
    "electron-count-save"
    "error"
    "image-display"
    "random-image"
    "sparse-frame-image-converter"
    "pva-converter"
    "pvapy-ad-sim-server"
)

# Function to check if a directory is in the build_dirs array
function is_included {
    local name="$1"
    local dir
    for dir in "${build_dirs[@]}"; do
        if [[ "$dir" == "$name" ]]; then
            return 0  # Found
        fi
    done
    return 1  # Not found
}

pids=()
for dir in "$SCRIPT_DIR"/*; do
    if [ -d "$dir" ]; then
        op_name=$(basename "$dir")
        # Check if the directory is in the list to build
        if ! is_included "$op_name"; then
            echo "Skipping $op_name as it's not in the build list"
            continue
        fi
        containerfile="$dir/Containerfile"
        if [ -f "$containerfile" ]; then
            echo "Found Containerfile for $op_name"
            echo "Building image for $op_name"
            # Start the build in background and collect its PID
            podman build -t "interactem/$op_name" -f "$containerfile" "$dir" &
            pids+=($!)
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