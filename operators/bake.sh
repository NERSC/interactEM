#!/bin/bash
SCRIPT_DIR=$(dirname "$0")
REPO_ROOT_DIR=$(git rev-parse --show-toplevel)
TAG=$(git rev-parse --short=6 HEAD)

cd $REPO_ROOT_DIR

# Build all images using Docker Bake
docker buildx bake base --file $REPO_ROOT_DIR/operators/docker-bake.hcl
docker buildx bake operator --file $REPO_ROOT_DIR/operators/docker-bake.hcl
docker buildx bake distiller-streaming --file $REPO_ROOT_DIR/operators/docker-bake.hcl
docker buildx bake operators --file $REPO_ROOT_DIR/operators/docker-bake.hcl --provenance=false

if [ $? -ne 0 ]; then
    echo "Failed to build images"
    exit 1
fi

generate_label_args() {
    local label_args=""
    # Process each operator directory
    for dir in "$REPO_ROOT_DIR/operators"/*; do
        if [ -d "$dir" ] && [ -f "$dir/operator.json" ] && [ -f "$dir/Containerfile" ]; then
            op_name=$(basename "$dir")

            # Get json
            operator_json=$(jq -c . "$dir/operator.json" 2>/dev/null)
            if [ $? -ne 0 ] || [ -z "$operator_json" ]; then
                continue
            fi
            # Add set argument using file instead of inline string
            label_args="${label_args} --set ${op_name}.labels.interactem.operator.spec='${operator_json}'"
        fi
    done
    
    echo "$label_args"
}

LABEL_ARGS=$(generate_label_args)
if [ -z "$LABEL_ARGS" ]; then
    echo "No operator.json files found or all are empty."
    exit 1
fi

# Create a temporary script because escaping json is hard
TMP_SCRIPT="/tmp/docker_buildx_script.sh"
cat > "$TMP_SCRIPT" << EOL
#!/bin/bash
docker buildx bake operators --file $REPO_ROOT_DIR/operators/docker-bake.hcl --push --provenance=false $LABEL_ARGS
EOL

chmod +x "$TMP_SCRIPT"
"$TMP_SCRIPT"
build_status=$?
rm -f "$TMP_SCRIPT"

if [ $build_status -ne 0 ]; then
    echo "Failed to build/push images"
    exit 1
fi