#!/bin/bash
set -e

SCRIPT_DIR=$(dirname "$0")
REPO_ROOT_DIR=$(git rev-parse --show-toplevel)
TAG=$(git rev-parse --short=6 HEAD)
OPERATORS_DIR="$REPO_ROOT_DIR/operators"
BAKE_FILE="$OPERATORS_DIR/docker-bake.hcl"
OPERATOR_JSON="operator.json"
VENV_DIR="$OPERATORS_DIR/distiller-streaming/.venv"

BUILD_BASE=false
PUSH_LOCAL=false
PUSH_REMOTE=false
PULL_LOCAL=false
DRY_RUN=false
TARGET=""

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --build-base)
            BUILD_BASE=true
            shift
            ;;
        --push-local)
            PUSH_LOCAL=true
            VARS="$OPERATORS_DIR/vars-local.hcl"
            shift
            ;;
        --pull-local)
            PULL_LOCAL=true
            shift
            ;;
        --push-remote)
            PUSH_REMOTE=true
            VARS="$OPERATORS_DIR/vars-prod.hcl"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --target)
            TARGET="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

if [ -z "$VARS" ]; then
    echo "Error: Must specify either --push-local or --push-remote"
    exit 1
fi

BASE_VARS="$OPERATORS_DIR/vars-base.hcl"

cd "$REPO_ROOT_DIR"


if $BUILD_BASE; then
    base_cmd=(docker buildx bake)
    if $DRY_RUN; then
        base_cmd+=(--print)
    fi
    echo "=== Building base images ==="
    "${base_cmd[@]}" base --file "$BAKE_FILE" \
        --file "$BASE_VARS"

    "${base_cmd[@]}" operator --file "$BAKE_FILE" \
        --file "$BASE_VARS"

    "${base_cmd[@]}" distiller-streaming --file "$BAKE_FILE" \
        --file "$BASE_VARS"
fi

#
# === Build operators ===
#
build_operators() {
    local cmd=(docker buildx bake)
    local has_labels=false
    
    if [ -n "$TARGET" ]; then
        cmd+=("$TARGET")
        cmd+=(--provenance=false)
    else
        cmd+=(operators)
    fi

    cmd+=(--file "$BAKE_FILE")
    cmd+=(--file "$VARS")
    
    # Add labels from operator.json files
    for dir in "$OPERATORS_DIR"/*; do
        if [ -d "$dir" ] && [ -f "$dir/$OPERATOR_JSON" ] && [ -f "$dir/Containerfile" ]; then
            op_name=$(basename "$dir")
            operator_json_file=$(jq -c . "$dir/$OPERATOR_JSON" 2>/dev/null)
            if [ $? -eq 0 ] && [ -n "$operator_json_file" ]; then
                cmd+=(--set "${op_name}.labels.interactem.operator.spec=${operator_json_file}")
                has_labels=true
            fi
        fi
    done
    
    # Check if we found any labels
    if [ "$has_labels" = false ]; then
        echo "No operator.json files found or all are empty."
        return 1
    fi
    
    cmd+=(--push)
    

    if $DRY_RUN; then
        cmd+=(--print)
    fi

    # Execute the command
    "${cmd[@]}"
}

echo "=== Building operators ==="
build_operators
build_status=$?

if [ $build_status -ne 0 ]; then
    echo "Failed to build/push images"
    exit 1
fi

#
# === Pull locally built images to podman ===
#
if $PUSH_LOCAL && $PULL_LOCAL; then
    echo "=== Pulling images back from local registry ==="
    cd $OPERATORS_DIR
    source $VENV_DIR/bin/activate
    poetry run python pull_images_from_bake.py
fi

echo "=== Done ==="