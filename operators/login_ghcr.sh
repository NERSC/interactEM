#!/bin/bash

export GH_USERNAME=<your_github_username>
export CR_PAT=$(cat ~/.ghcr_pat) # PAT with read:packages and write:packages scopes
DOCKER=podman # or docker


if [ -z "$CR_PAT" ]; then
  echo "Error: CR_PAT is empty. Please check your GitHub PAT."
  exit 1
fi

echo $CR_PAT | $DOCKER login ghcr.io -u $GH_USERNAME --password-stdin