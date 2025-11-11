#!/bin/bash

find_podman_socket() {
    # Method 1: Check if podman info provides socket info (newer versions)
    if command -v podman &> /dev/null; then
        socket_path=$(podman info --format '{{.Host.RemoteSocket.Path}}' 2>/dev/null)
        if [ -n "$socket_path" ] && [ -e "$socket_path" ]; then
            echo "$socket_path"
            return 0
        fi
    fi

    # Method 2: Check for user systemd socket (common on Linux)
    if systemctl --user is-active podman.socket &>/dev/null; then
        socket_path="/run/user/$(id -u)/podman/podman.sock"
        if [ -e "$socket_path" ]; then
            echo "$socket_path"
            return 0
        fi
    fi

    # Method 3: Check for system-wide podman socket
    if systemctl is-active podman.socket &>/dev/null; then
        socket_path="/run/podman/podman.sock"
        if [ -e "$socket_path" ]; then
            echo "$socket_path"
            return 0
        fi
    fi

    # Method 4: Check for podman machine (macOS/Windows with podman machine)
    if command -v podman &> /dev/null && podman machine list &>/dev/null 2>&1; then
        # Get current machine name
        machine_name=$(podman machine info --format "{{.Host.CurrentMachine}}" 2>/dev/null)
        if [ -n "$machine_name" ]; then
            # Try to extract socket path without jq
            socket_path=$(podman machine inspect "$machine_name" 2>/dev/null | grep -A1 '"PodmanSocket"' | grep '"Path"' | sed 's/.*"Path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
            if [ -n "$socket_path" ] && [ -e "$socket_path" ]; then
                echo "$socket_path"
                return 0
            fi
        fi
    fi

    # Method 5: Check common default locations
    common_paths=(
        "/run/user/$(id -u)/podman/podman.sock"
        "$XDG_RUNTIME_DIR/podman/podman.sock"
        "$HOME/.local/share/containers/podman/machine/podman.sock"
        "/var/run/podman/podman.sock"
        "/run/podman/podman.sock"
    )

    for path in "${common_paths[@]}"; do
        if [ -e "$path" ]; then
            echo "$path"
            return 0
        fi
    done

    # If nothing found
    echo "Error: Could not find podman socket" >&2
    echo "You may need to start podman.socket service:" >&2
    echo "  systemctl --user start podman.socket  # for rootless" >&2
    echo "  sudo systemctl start podman.socket    # for rootful" >&2
    return 1
}

# Main execution
PODMAN_SOCKET=$(find_podman_socket)

if [ $? -eq 0 ]; then
    # Format as unix:// URI and output it
    PODMAN_SERVICE_URI="unix://${PODMAN_SOCKET}"
    echo "$PODMAN_SERVICE_URI"
else
    exit 1
fi