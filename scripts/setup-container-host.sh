#!/bin/bash
set -euo pipefail

GIT_ROOT="$(git rev-parse --show-toplevel)"
CREDS="${GIT_ROOT}/conf/nats-conf/out_jwt/backend.creds"
CONTAINER_CREDS="/tmp/backend.creds"

# we detect container host by attempting to connect to NATS
# this means nats should be running locally before calling this script
# this should be be run if we do make docker-up
HOST=""
for h in host.containers.internal localhost; do
    echo "Testing $h..." >&2
    OUTPUT=$(podman run --rm --network=host -v "${CREDS}:${CONTAINER_CREDS}:ro" \
        docker.io/natsio/nats-box nats rtt \
        --server="nats://$h:4222" --timeout=1s --creds="$CONTAINER_CREDS" 2>&1)

    if echo "$OUTPUT" | grep -q "failed\|error\|no such host"; then
        echo "$OUTPUT" >&2
        echo "Failed to connect via $h" >&2
    else
        HOST=$h
        echo "Connected via $h" >&2
        break
    fi
done

[ -z "$HOST" ] && { 
    echo -e "\nERROR: Cannot connect to NATS on either host.containers.internal or localhost." >&2
    echo "ERROR: Sometimes, this means that docker/podman networking is borked and you should try a system reboot..." >&2
    exit 1
}
echo "Container host: $HOST"

# depending on which host we detected (localhost or host.containers.internal)
# we need to update .env files to use that host inside containers
# we look for all .env.example files and update corresponding .env files
# replacing any instance of host.containers.internal with the detected host

# this is claude-generated, no chance I could do this: 's/[\/&]/\\&/g'
while IFS= read -r example; do
    env="${example%.example}"
    [ -f "$env" ] || continue

    updated=false
    while IFS='=' read -r key val || [ -n "$key" ]; do
        [[ -z "$key" || "$key" =~ ^# ]] && continue
        [[ "$val" == *"host.containers.internal"* ]] || continue

        new_val="${val//host.containers.internal/$HOST}"
        sed_escaped=$(printf '%s\n' "$new_val" | sed 's/[\/&]/\\&/g')

        if grep -q "^${key}=" "$env"; then
            current=$(grep "^${key}=" "$env" | cut -d'=' -f2-)
            [ "$current" != "$new_val" ] && {
                sed -i.bak "s|^${key}=.*|${key}=${sed_escaped}|" "$env"
                updated=true
            }
        else
            echo "${key}=${new_val}" >> "$env"
            updated=true
        fi
    done < "$example"

    rm -f "${env}.bak"
    [ "$updated" = true ] && echo "Updated ${env#$GIT_ROOT/}"
done < <(find "$GIT_ROOT" -name ".env.example" -type f)

echo "Container host configuration complete"