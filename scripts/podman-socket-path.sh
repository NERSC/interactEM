#!/bin/bash

podman machine inspect $(podman machine info --format "{{.Host.CurrentMachine}}") | jq -r '.[0].ConnectionInfo.PodmanSocket.Path'