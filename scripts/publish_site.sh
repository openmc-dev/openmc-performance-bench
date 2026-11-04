#!/usr/bin/env bash
#
# Build the published site: the performance dashboard at the root and the
# full ASV report under asv/.
#
# Usage: scripts/publish_site.sh <results repo dir> <output dir> <machine name>
#
# ASV reads results from .asv/results, which the caller must point at
# <results repo dir>/results. The dashboard caches commit titles/PRs in
# <results repo dir>/dashboard/commit_info.json; set GH_TOKEN to avoid GitHub
# API rate limits when filling it. If the dashboard fails to build, a redirect
# to the ASV report is written instead so the report is always published.

set -euo pipefail

if [ $# -ne 3 ]; then
  echo "Usage: $0 <results repo dir> <output dir> <machine name>" >&2
  exit 2
fi
RESULTS_REPO=$1
OUT=$2
MACHINE=$3
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# ASV must read the same results as the dashboard
ASV_RESULTS=$(cd .asv/results 2>/dev/null && pwd -P) || ASV_RESULTS=""
REPO_RESULTS=$(cd "$RESULTS_REPO/results" && pwd -P)
if [ "$ASV_RESULTS" != "$REPO_RESULTS" ]; then
  echo "Error: .asv/results must point at $RESULTS_REPO/results" >&2
  exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT"
asv publish --html-dir "$OUT/asv"

mkdir -p "$RESULTS_REPO/dashboard"
if ! python "$SCRIPT_DIR/../dashboard/build_site.py" \
    --results-dir "$RESULTS_REPO/results/$MACHINE" \
    --output "$OUT" \
    --commit-cache "$RESULTS_REPO/dashboard/commit_info.json"; then
  echo "::warning::Dashboard build failed; publishing the ASV report only"
  cat > "$OUT/index.html" <<'EOF'
<!doctype html>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=asv/">
<title>OpenMC performance</title>
<p><a href="asv/">OpenMC benchmark results</a></p>
EOF
fi
