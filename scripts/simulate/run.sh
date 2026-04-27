#!/usr/bin/env bash
# Convenience wrapper to run simulation inside the FastAPI container.
#
# Usage (from project root or anywhere on VM):
#   ./scripts/simulate/run.sh --only reset
#   ./scripts/simulate/run.sh --only setup
#   ./scripts/simulate/run.sh --only reset,setup
#   ./scripts/simulate/run.sh --only auth,browse,cart,checkout
#   ./scripts/simulate/run.sh                # full run
#
# All arguments are forwarded to runner.py.
# Defaults: --target http://localhost:8000 --skip-stripe-check --report-dir /tmp/sim-reports
#
# After each run, the latest HTML report is copied to ./sim-report.html
# so you can open it in a browser or serve it.

CONTAINER="boilerplate-app-fastapi-1"
DEFAULT_TARGET="http://localhost:8000"
CONTAINER_REPORT_DIR="/tmp/sim-reports"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "ERROR: Container '${CONTAINER}' is not running."
    echo "Start it with: docker compose up -d"
    exit 1
fi

# Build args: inject defaults only if not already provided by user
ARGS=("$@")

# Add --target default if not provided
if ! printf '%s\n' "${ARGS[@]}" | grep -q -- '--target'; then
    ARGS=("--target" "$DEFAULT_TARGET" "${ARGS[@]}")
fi

# Add --report-dir default if not provided
if ! printf '%s\n' "${ARGS[@]}" | grep -q -- '--report-dir'; then
    ARGS=("${ARGS[@]}" "--report-dir" "$CONTAINER_REPORT_DIR")
fi

# Add --skip-stripe-check default if not provided
if ! printf '%s\n' "${ARGS[@]}" | grep -q -- '--skip-stripe-check'; then
    ARGS=("${ARGS[@]}" "--skip-stripe-check")
fi

# Run simulation
docker exec -it "$CONTAINER" python scripts/simulate/runner.py "${ARGS[@]}"
EXIT_CODE=$?

# Copy latest report out of container
LATEST=$(docker exec "$CONTAINER" sh -c "ls -td ${CONTAINER_REPORT_DIR}/sim-* 2>/dev/null | head -1")
if [ -n "$LATEST" ]; then
    # Determine project root (where this script lives: scripts/simulate/run.sh)
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
    LOCAL_REPORTS="$PROJECT_ROOT/reports"
    mkdir -p "$LOCAL_REPORTS"

    # Copy the entire report directory out
    REPORT_NAME=$(basename "$LATEST")
    docker cp "$CONTAINER:$LATEST" "$LOCAL_REPORTS/$REPORT_NAME" 2>/dev/null

    # Copy latest HTML as a convenient top-level file
    if docker exec "$CONTAINER" test -f "$LATEST/report.html" 2>/dev/null; then
        docker cp "$CONTAINER:$LATEST/report.html" "$LOCAL_REPORTS/latest-report.html" 2>/dev/null
        echo ""
        echo "HTML report: $LOCAL_REPORTS/$REPORT_NAME/report.html"
        echo "Latest link: $LOCAL_REPORTS/latest-report.html"
    fi
fi

exit $EXIT_CODE
