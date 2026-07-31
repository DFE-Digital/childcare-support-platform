#!/bin/bash
set -euo pipefail

# -----------------------------------------------------------------------------
# GitHub Actions Runner bootstrap for Amazon Linux 2023
# Retrieves the PAT from SSM SecureString at boot - never stored in plaintext.
# -----------------------------------------------------------------------------

# Install dependencies
dnf install -y docker git libicu jq

# Enable and start Docker
systemctl enable --now docker
usermod -aG docker ec2-user

# Retrieve GitHub PAT from SSM (IMDSv2 region fetch)
REGION="${aws_region}"
PAT=$(aws ssm get-parameter \
  --name "${ssm_pat_name}" \
  --with-decryption \
  --region "$REGION" \
  --query "Parameter.Value" \
  --output text)

# Create runner user and working directory
useradd -m -s /bin/bash runner || true
RUNNER_HOME=/home/runner/actions-runner
mkdir -p "$RUNNER_HOME"
cd "$RUNNER_HOME"

# Download latest GitHub Actions runner
RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest \
  | jq -r '.tag_name' | sed 's/v//')
curl -fsSL \
  "https://github.com/actions/runner/releases/download/v$${RUNNER_VERSION}/actions-runner-linux-x64-$${RUNNER_VERSION}.tar.gz" \
  -o runner.tar.gz
tar xzf runner.tar.gz
rm runner.tar.gz
chown -R runner:runner "$RUNNER_HOME"

# Register runner with GitHub (unattended)
sudo -u runner ./config.sh \
  --url "https://github.com/${github_org}/${github_repo}" \
  --token "$PAT" \
  --name "${project}-${environment}-runner" \
  --labels "${project},${environment}" \
  --unattended \
  --replace

# Install and start as a systemd service
./svc.sh install runner
./svc.sh start runner
