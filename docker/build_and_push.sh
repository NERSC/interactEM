#!/bin/bash

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(git rev-parse --show-toplevel)
TAG=$(git rev-parse --short=6 HEAD)
ORG=${1:-interactem}

$SCRIPT_DIR/build.sh $ORG
if [ $? -ne 0 ]; then
    echo "Failed to build images"
    exit 1
fi

docker push $ORG/operator:$TAG 
docker push $ORG/operator:latest