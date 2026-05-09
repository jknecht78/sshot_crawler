#!/bin/bash
set -e
PROJECT_DIR="/home/jhums/DEV/speed"

source "$PROJECT_DIR/.venv/bin/activate"

# Start the inference server in the background
bash "$PROJECT_DIR/server.sh" &
SERVER_PID=$!

# Wait until the API is accepting connections (bail out if server process dies)
until curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "ERROR: Server process exited before becoming ready."
        exit 1
    fi
    sleep 2
done
echo "Server ready."

# Run the crawler
python "$PROJECT_DIR/main.py" "$@"
EXIT_CODE=$?

# Shut the server down when the crawler finishes
kill "$SERVER_PID" 2>/dev/null
wait "$SERVER_PID" 2>/dev/null || true

exit $EXIT_CODE

