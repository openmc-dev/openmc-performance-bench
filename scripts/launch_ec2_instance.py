"""Launch instance on AWS EC2"""

import time
import socket
import subprocess
import boto3


# Define parameters.
IMAGE_ID = 'ami-0a54ff6f081ad46ae' # Ubuntu 25.04, us-east-1, amd64
KEYPAIR_NAME = 'X1 Carbon 2022'
SECURITY_GROUP = 'sg-130bcb6b'

# Connect to EC2.
ec2 = boto3.client('ec2', region_name='us-east-1')

# SSH/SCP configuration for post-launch file copy
SSH_USERNAME = 'ubuntu'  # default for Ubuntu AMIs

# Configure up to two files to copy to the instance (leave empty to skip)
FILES_TO_COPY = [
    'gklib_fix.patch',
    'setup_ami.sh',
]
REMOTE_DEST_DIR = f'/home/{SSH_USERNAME}/'

# Utility: wait until SSH port is reachable
def wait_for_ssh(host: str, port: int = 22, timeout: int = 300, interval: int = 5) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=5):
                return True
        except OSError:
            time.sleep(interval)
    return False

# Utility: copy files via scp with retries
def scp_files(host: str, username: str, files: list[str], dest_dir: str,
              attempts: int = 10, delay: int = 5) -> bool:
    if not files:
        print("No files configured to copy; skipping.")
        return False
    target = f"{username}@{host}:{dest_dir}"
    base_cmd = [
        'scp',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'BatchMode=yes',
    ]
    for attempt in range(1, attempts + 1):
        try:
            cmd = base_cmd + files + [target]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                print(f"Copied files to {target}")
                return True
            else:
                print(f"SCP attempt {attempt} failed: {res.stderr.strip()}")
        except Exception as e:
            print(f"SCP attempt {attempt} raised: {e}")
        time.sleep(delay)
    return False

# Desired root volume size in GiB (increase above the AMI default of ~8 GiB)
ROOT_VOLUME_SIZE_GB = 32  # adjust as needed

# Build BlockDeviceMappings to enlarge the root volume while preserving AMI settings
try:
    img_desc = ec2.describe_images(ImageIds=[IMAGE_ID])
    images = img_desc.get('Images', [])
    if not images:
        raise RuntimeError(f"AMI not found: {IMAGE_ID}")
    image = images[0]
    root_device_name = image.get('RootDeviceName', '/dev/sda1')
    base_mappings = image.get('BlockDeviceMappings', [])

    block_device_mappings = []
    for m in base_mappings:
        entry = {'DeviceName': m['DeviceName']}
        if 'Ebs' in m:
            ebs = dict(m['Ebs'])  # copy existing settings (SnapshotId, Encrypted, KmsKeyId, etc.)
            if m['DeviceName'] == root_device_name:
                # Expand root volume: keep existing type, snapshot, encryption, etc.; just bump size
                current_size = ebs.get('VolumeSize', 8)
                ebs['VolumeSize'] = max(current_size, ROOT_VOLUME_SIZE_GB)
                # Ensure sane defaults present
                ebs.setdefault('DeleteOnTermination', True)
                ebs.setdefault('VolumeType', ebs.get('VolumeType', 'gp3'))
            entry['Ebs'] = ebs
        elif 'VirtualName' in m:
            entry['VirtualName'] = m['VirtualName']
        block_device_mappings.append(entry)
except Exception:
    # Fallback: if describe_images fails for some reason, at least attempt to override common root device
    root_device_name = '/dev/sda1'
    block_device_mappings = [{
        'DeviceName': root_device_name,
        'Ebs': {
            'VolumeSize': ROOT_VOLUME_SIZE_GB,
            'VolumeType': 'gp3',
            'DeleteOnTermination': True,
        }
    }]

# Launch the instance
resp = ec2.run_instances(
    ImageId=IMAGE_ID,
    MinCount=1,
    MaxCount=1,
    InstanceType='c7i-flex.large',
    SecurityGroupIds=(SECURITY_GROUP,),
    KeyName=KEYPAIR_NAME,
    BlockDeviceMappings=block_device_mappings,
  )

# Collect instance IDs from the launch response
instance_ids = [inst['InstanceId'] for inst in resp['Instances']]
print("Launched instance(s):", ", ".join(instance_ids))

# Wait until the instance(s) are in 'running' state so that networking details are assigned
waiter = ec2.get_waiter('instance_running')
print("Waiting for instance(s) to enter 'running' state…")
waiter.wait(InstanceIds=instance_ids)

# After running, query EC2 for the latest details. PublicDnsName may take a short while to appear
# even after the instance is running, so poll briefly until it shows up or we time out.

def _describe_instances_by_id(client, ids):
    desc = client.describe_instances(InstanceIds=ids)
    details = []
    for res in desc.get('Reservations', []):
        for inst in res.get('Instances', []):
            details.append({
                'InstanceId': inst.get('InstanceId'),
                'PrivateIpAddress': inst.get('PrivateIpAddress'),
                'PublicIpAddress': inst.get('PublicIpAddress'),
                'PublicDnsName': inst.get('PublicDnsName'),
                'State': inst.get('State', {}).get('Name')
            })
    return details

deadline = time.time() + 180  # up to 3 minutes
details = _describe_instances_by_id(ec2, instance_ids)
while any(not d.get('PublicDnsName') for d in details) and time.time() < deadline:
    time.sleep(3)
    details = _describe_instances_by_id(ec2, instance_ids)

for d in details:
    print(f"InstanceId: {d.get('InstanceId')}")
    print(f"State:      {d.get('State')}")
    print(f"Private IP: {d.get('PrivateIpAddress')}")
    print(f"Public IP:  {d.get('PublicIpAddress')}")
    print(f"Public DNS: {d.get('PublicDnsName')}")
    print()

    # Attempt to copy files to the instance once SSH is reachable
    host = d.get('PublicDnsName') or d.get('PublicIpAddress')
    if host:
        print(f"Waiting for SSH on {host}…")
        if wait_for_ssh(host):
            print(f"SSH reachable on {host}. Copying files (if configured)…")
            scp_files(host, SSH_USERNAME, FILES_TO_COPY, REMOTE_DEST_DIR)
        else:
            print(f"SSH not reachable on {host} within timeout; skipping file copy.")
    else:
        print("No public address found for instance; skipping file copy.")
