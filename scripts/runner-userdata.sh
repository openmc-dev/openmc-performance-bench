#!/bin/bash
# User-data script for ephemeral GitHub Actions runner on EC2.
# This script is rendered as a template by launch_ec2_instance.py,
# which substitutes RUNNER_TOKEN and RUNNER_LABEL before passing it
# to EC2 as user-data.

set -euxo pipefail

GITHUB_REPO_URL="https://github.com/openmc-dev/openmc-performance-bench"
RUNNER_LABEL="${RUNNER_LABEL}"        # substituted at launch time
RUNNER_TOKEN="${RUNNER_TOKEN}"        # substituted at launch time
RUNNER_VERSION="2.323.0"
RUNNER_USER="ubuntu"
RUNNER_HOME="/home/${RUNNER_USER}/actions-runner"

# Install the runner app
mkdir -p "${RUNNER_HOME}"
cd "${RUNNER_HOME}"

curl -fsSL -o runner.tar.gz \
  "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
tar xzf runner.tar.gz
rm runner.tar.gz
chown -R "${RUNNER_USER}:${RUNNER_USER}" "${RUNNER_HOME}"

# Register as an ephemeral runner
# --ephemeral: runner deregisters itself after completing exactly one job.
su - "${RUNNER_USER}" -c "
  cd '${RUNNER_HOME}'
  ./config.sh \
    --url '${GITHUB_REPO_URL}' \
    --token '${RUNNER_TOKEN}' \
    --labels '${RUNNER_LABEL}' \
    --name 'ec2-ephemeral-\$(hostname)' \
    --ephemeral \
    --unattended \
    --disableupdate
"

# Run the runner (blocks until the one job completes)
su - "${RUNNER_USER}" -c "cd '${RUNNER_HOME}' && ./run.sh"
STATUS=$?

echo "Runner exited with status: $STATUS"

shutdown -h now
exit $STATUS
