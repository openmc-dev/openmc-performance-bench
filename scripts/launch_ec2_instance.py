"""
Launch an ephemeral EC2 instance pre-configured as a GitHub Actions
self-hosted runner for openmc-dev/openmc-performance-bench.

Usage (called from the GHA workflow or locally):
    python scripts/launch_ec2_instance.py \
        --runner-token <short-lived-GHA-token> \
        --runner-label <label>

The script prints the launched instance ID to stdout so the calling
workflow can capture it for later termination.
"""

import argparse
import socket
import sys
import time
from pathlib import Path

import boto3

# ---------------------------------------------------------------------------
# Configuration — edit these to match your account / AMI
# ---------------------------------------------------------------------------
IMAGE_ID        = "ami-0287117f4444aee01"
INSTANCE_TYPE   = "c7i-flex.xlarge"
KEYPAIR_NAME    = None                     # Optional; set to None to omit
SECURITY_GROUP  = "sg-0e7103cd0b94e4291"
REGION          = "us-east-2"
ROOT_VOLUME_GB  = 100

USERDATA_TEMPLATE = Path(__file__).parent / "runner-userdata.sh"
# ---------------------------------------------------------------------------


def build_user_data(runner_token: str, runner_label: str, github_repo: str) -> str:
    """Read the runner-userdata.sh template and substitute variables."""
    template = USERDATA_TEMPLATE.read_text()
    script = (
        template
        .replace('"__RUNNER_TOKEN__"', runner_token)
        .replace('"__RUNNER_LABEL__"', runner_label)
        .replace('"__GITHUB_REPO__"', github_repo)
    )
    return script


def get_block_device_mappings(ec2_client) -> list:
    """Copy the AMI's root device mapping, expanding the root volume."""
    try:
        images = ec2_client.describe_images(ImageIds=[IMAGE_ID])["Images"]
        if not images:
            raise RuntimeError(f"AMI not found: {IMAGE_ID}")
        image = images[0]
        root_device = image.get("RootDeviceName", "/dev/sda1")
        mappings = []
        for m in image.get("BlockDeviceMappings", []):
            entry = {"DeviceName": m["DeviceName"]}
            if "Ebs" in m:
                ebs = dict(m["Ebs"])
                if m["DeviceName"] == root_device:
                    ebs["VolumeSize"] = max(ebs.get("VolumeSize", 8), ROOT_VOLUME_GB)
                    ebs.setdefault("DeleteOnTermination", True)
                    ebs.setdefault("VolumeType", "gp3")
                entry["Ebs"] = ebs
            elif "VirtualName" in m:
                entry["VirtualName"] = m["VirtualName"]
            mappings.append(entry)
        return mappings
    except Exception:
        return [{
            "DeviceName": "/dev/sda1",
            "Ebs": {
                "VolumeSize": ROOT_VOLUME_GB,
                "VolumeType": "gp3",
                "DeleteOnTermination": True,
            },
        }]


def wait_for_running(ec2_client, instance_id: str) -> dict:
    print(f"Waiting for {instance_id} to enter 'running' state…", flush=True)
    waiter = ec2_client.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id])
    desc = ec2_client.describe_instances(InstanceIds=[instance_id])
    return desc["Reservations"][0]["Instances"][0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner-token", required=True,
                        help="Short-lived GitHub Actions runner registration token")
    parser.add_argument("--runner-label", default="perf-ec2",
                        help="Label(s) to attach to the runner (comma-separated)")
    parser.add_argument("--github-repo", default='openmc-dev/openmc-performance-bench',
                        help="GitHub repository in owner/repo form")
    args = parser.parse_args()

    ec2 = boto3.client("ec2", region_name=REGION)

    run_kwargs = dict(
        ImageId=IMAGE_ID,
        MinCount=1,
        MaxCount=1,
        InstanceType=INSTANCE_TYPE,
        SecurityGroupIds=[SECURITY_GROUP],
        UserData=build_user_data(
            args.runner_token,
            args.runner_label,
            args.github_repo
        ),
        BlockDeviceMappings=get_block_device_mappings(ec2),
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": "openmc-perf-runner"}],
        }],
    )
    if KEYPAIR_NAME:
        run_kwargs["KeyName"] = KEYPAIR_NAME

    resp = ec2.run_instances(**run_kwargs)
    instance_id = resp["Instances"][0]["InstanceId"]
    print(f"Launched: {instance_id}", flush=True)

    instance = wait_for_running(ec2, instance_id)
    print(f"Public IP:  {instance.get('PublicIpAddress', 'N/A')}", flush=True)
    print(f"Public DNS: {instance.get('PublicDnsName', 'N/A')}", flush=True)

    # Emit the instance ID on its own line so the workflow can capture it easily
    print(f"instance_id={instance_id}", flush=True)


if __name__ == "__main__":
    main()
