#!/bin/bash
# Check if the current user can run docker commands

if ! docker ps > /dev/null 2>&1; then
	echo "Error: Unable to run 'docker ps' as current user" >&2
	echo "" >&2
	echo "You have two options:" >&2
	echo "1. Run docker commands with sudo (e.g., 'sudo make docker-up')" >&2
	echo "2. Configure Docker to run without sudo by following: https://docs.docker.com/engine/install/linux-postinstall/" >&2
	echo "" >&2
	exit 1
fi
