#!/bin/bash
set -e

# Function to handle shutdown
cleanup() {
    echo ""
    echo "⚠️  Shutting down agents..."
    kill $METRIC_PID $FILE_PID 2>/dev/null
    wait $METRIC_PID $FILE_PID 2>/dev/null
    echo "✅ All agents stopped"
    exit 0
}

trap cleanup SIGTERM SIGINT

cd /app/metric-agent
python -m core.agent &
METRIC_PID=$!

cd /app/file-agent
python main.py listen &
FILE_PID=$!

# Wait for both processes
wait $METRIC_PID $FILE_PID