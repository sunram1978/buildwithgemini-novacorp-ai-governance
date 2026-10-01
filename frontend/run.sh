#!/bin/bash
# run.sh - Helper script to run the frontend proxy

# Extract the most recent Agent Engine ID from deployment metadata
METADATA_FILE="../deployment_metadata.json"

if [ -f "$METADATA_FILE" ]; then
    # Try to get the pending operation engine ID if deploying, otherwise the remote_agent_runtime_id
    PENDING_ID=$(cat "$METADATA_FILE" | grep -o '"operation_name": "[^"]*"' | grep -o 'reasoningEngines/[^/]*' | cut -d'/' -f2 | head -1)
    
    if [ ! -z "$PENDING_ID" ]; then
        # Reconstruct the resource name from pending operation
        PENDING_LOC=$(cat "$METADATA_FILE" | grep '"location"' | head -1 | awk -F '"' '{print $4}')
        PENDING_PROJ=$(cat "$METADATA_FILE" | grep -A 5 '"pending_operation"' | grep '"project"' | awk -F '"' '{print $4}')
        # We need the project number for the resource name, which is 1044488595817
        export AGENT_ENGINE_RESOURCE_NAME="projects/1044488595817/locations/${PENDING_LOC}/reasoningEngines/${PENDING_ID}"
    else
        export AGENT_ENGINE_RESOURCE_NAME=$(cat "$METADATA_FILE" | grep '"remote_agent_runtime_id"' | awk -F '"' '{print $4}')
    fi
else
    # Fallback to the known pending reasoning engine ID
    export AGENT_ENGINE_RESOURCE_NAME="projects/1044488595817/locations/us-east1/reasoningEngines/2956118375136231424"
fi

# Set the agent directory matching agents-cli-manifest.yaml
export AGENT_DIRECTORY="app"

echo "Using AGENT_ENGINE_RESOURCE_NAME: $AGENT_ENGINE_RESOURCE_NAME"
echo "Using AGENT_DIRECTORY: $AGENT_DIRECTORY"

# Create a virtual environment for the frontend if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate and install requirements
source .venv/bin/activate
pip install -r requirements.txt

# Run the proxy
python main.py
