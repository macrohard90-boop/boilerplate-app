#!/usr/bin/env bash
# Push to a secondary remote (e.g., GitLab mirror).
# Usage: bash scripts/mirror.sh [remote-name]
#
# Setup:
#   git remote add mirror git@gitlab.com:user/repo.git
#   bash scripts/mirror.sh mirror

set -euo pipefail

REMOTE="${1:-mirror}"

if ! git remote get-url "$REMOTE" > /dev/null 2>&1; then
    echo "Error: Remote '$REMOTE' not found."
    echo "Add it first: git remote add $REMOTE <url>"
    exit 1
fi

echo "Pushing all branches and tags to '$REMOTE'..."
git push "$REMOTE" --all
git push "$REMOTE" --tags
echo "Mirror push complete."
