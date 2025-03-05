#!/bin/bash


# Get the directory of this script
SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(git rev-parse --show-toplevel)
TAG=$(git rev-parse --short=6 HEAD)
ORG=${1:-interactem}
PODMAN=${2:-p}

# Clean up any existing temp files before starting
rm -f /tmp/build_operator_*.log /tmp/build_operator_*.exit

# Build base containers
echo "Building base containers..."
$ROOT_DIR/docker/build.sh $ORG $PODMAN
if [ $? -ne 0 ]; then
    echo "Failed to build base containers."
    exit 1
fi

if [ $PODMAN == "p" ]; then
    DOCKER=podman
    platform=$(uname -m)
    if [ $platform == "x86_64" ]; then
        PLATFORM="--platform=linux/amd64"
    elif [ $platform == "aarch64" ]; then
        PLATFORM="--platform=linux/arm64"
    elif [ $platform == "arm64" ]; then
        PLATFORM="--platform=linux/arm64"
    else
        echo "Unsupported platform: $platform"
        exit 1
    fi
else
    DOCKER=docker
    PLATFORM="--platform=linux/amd64,linux/arm64"
fi

build_dirs=(
    "beam-compensation"
    "data-replay"
    "detstream-aggregator"
    "detstream-assembler"
    "detstream-producer"
    "detstream-state-server"
    "electron-count"
    "electron-count-save"
    "error"
    "image-display"
    "pva-converter"
    "pvapy-ad-sim-server"
    "random-image"
    "sparse-frame-image-converter"
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

# Extract last N lines from log file where the error likely occurred
function extract_error_context {
    local logfile="$1"
    local lines=${2:-25}  # Default to last 25 lines
    
    if [ -s "$logfile" ]; then
        echo "Error context (last $lines lines):"
        echo "--------------------------------------------------------------------------------"
        tail -n "$lines" "$logfile"
        echo "--------------------------------------------------------------------------------"
    else
        echo "No log data available."
    fi
}

# Build function for operators
build_operator() {
    local op_name=$1
    local containerfile=$2
    local dir=$3
    local logfile="/tmp/build_operator_${op_name}.log"
    
    # Make sure operator.json exists and can be parsed
    if [ ! -f "$dir/operator.json" ]; then
        echo "Error: operator.json not found for $op_name" > "$logfile"
        echo "1" > "/tmp/build_operator_${op_name}.exit"
        return 1
    fi
    
    # Try to parse operator.json, capture errors
    local operator_json=""
    operator_json=$(jq -c . "$dir/operator.json" 2>"$logfile")
    if [ $? -ne 0 ]; then
        echo "Error: Failed to parse operator.json for $op_name" >> "$logfile"
        echo "1" > "/tmp/build_operator_${op_name}.exit"
        return 1
    fi
    
    # Run the build and capture the exit code directly
    echo "Starting build for operator ghcr.io/nersc/interactem/$op_name ..."
    $DOCKER build $PLATFORM \
        -t "ghcr.io/nersc/interactem/$op_name" \
        -f "$containerfile" \
        --label "interactem.operator.spec=$operator_json" \
        "$dir" > "$logfile" 2>&1
    
    local status=$?
    echo "$status" > "/tmp/build_operator_${op_name}.exit"
    return $status
}

# Start all builds in parallel
echo "Starting operator builds..."
operators_to_build=()
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
            operators_to_build+=("$op_name")
            build_operator "$op_name" "$containerfile" "$dir" &
        else
            echo "No Containerfile in $dir, skipping"
        fi
    fi
done

# Wait for all background processes to complete
echo "Waiting for all builds to complete..."
wait

# Check results and report success first
echo "Checking build results..."
successful_builds=0
failed_builds=0
failed_operators=()

for op_name in "${operators_to_build[@]}"; do
    # Check if exit file exists
    if [ ! -f "/tmp/build_operator_${op_name}.exit" ]; then
        echo "Error: Build process for ${op_name} didn't complete properly"
        failed_builds=$((failed_builds + 1))
        failed_operators+=("$op_name")
        continue
    fi
    
    exit_code=$(cat "/tmp/build_operator_${op_name}.exit" 2>/dev/null || echo "1")
    if [ "$exit_code" == "0" ]; then
        echo "✓ Build succeeded for operator ${op_name}"
        successful_builds=$((successful_builds + 1))
    else
        echo "✗ Build failed for operator ${op_name}"
        failed_builds=$((failed_builds + 1))
        failed_operators+=("$op_name")
    fi
done

# Summary of build results
echo ""
echo "Build Summary:"
echo "- Successful builds: $successful_builds"
echo "- Failed builds: $failed_builds"
echo "- Total operators: ${#operators_to_build[@]}"
echo ""

# Handle failures one by one with detailed error information
if [ ${#failed_operators[@]} -gt 0 ]; then
    echo "Detailed error information for failed builds:"
    echo ""
    
    for op_name in "${failed_operators[@]}"; do
        echo "==== ERROR: ${op_name} build failed ===="
        logfile="/tmp/build_operator_${op_name}.log"
        
        if [ -f "$logfile" ]; then
            extract_error_context "$logfile" 20
        else
            echo "Log file not found for $op_name"
        fi
        echo ""
    done
    
    echo "One or more operator builds failed"
    failed=1
else
    echo "All operator builds completed successfully"
    failed=0
fi

# Cleanup
echo "Cleaning up temporary files..."
rm -f /tmp/build_operator_*.log /tmp/build_operator_*.exit

exit $failed