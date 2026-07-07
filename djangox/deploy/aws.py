import atexit
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import boto3


def session(profile_name=None, region_name='ap-northeast-2'):
    if profile_name:
        return boto3.session.Session(profile_name=profile_name,
                                     region_name=region_name)
    return boto3.session.Session(region_name=region_name)


def client(service_name, profile_name=None, region_name='ap-northeast-2'):
    return session(profile_name, region_name).client(service_name)


def temporary_ssh_key():
    directory = Path(tempfile.mkdtemp(prefix='djangox-eic-'))
    private_key = directory / 'id_ed25519'
    command = ['ssh-keygen', '-t', 'ed25519', '-N', '', '-f',
               private_key.as_posix(), '-q']
    subprocess.run(command, check=True)
    atexit.register(shutil.rmtree, directory)
    return private_key.as_posix(), private_key.with_suffix('.pub').read_text().strip()


def send_ssh_public_key(instance, os_user, public_key, profile_name=None,
                        region_name='ap-northeast-2'):
    response = client('ec2-instance-connect', profile_name,
                      region_name).send_ssh_public_key(
        InstanceId=instance['InstanceId'],
        InstanceOSUser=os_user,
        SSHPublicKey=public_key,
        AvailabilityZone=instance['Placement']['AvailabilityZone'],
    )
    if not response['Success']:
        raise RuntimeError(f"Failed to send SSH public key to {instance['InstanceId']}")
    return response


def temporary_instance_connect_key(instances, os_user, profile_name=None,
                                   region_name='ap-northeast-2'):
    private_key, public_key = temporary_ssh_key()
    for instance in instances:
        send_ssh_public_key(instance, os_user, public_key, profile_name, region_name)
    return private_key


def tag_value(resource, name):
    for tag in resource.get('Tags', []):
        if tag.get('Key') == name:
            return tag.get('Value', '')
    return ''


def running_instances(project_name, profile_name=None, region_name='ap-northeast-2',
                      tag_name='project'):
    response = client('ec2', profile_name, region_name).describe_instances(
        Filters=[
            {'Name': f'tag:{tag_name}', 'Values': [project_name]},
            {'Name': 'instance-state-name', 'Values': ['running']},
        ]
    )
    return [
        instance
        for reservation in response['Reservations']
        for instance in reservation['Instances']
    ]


def secret_values(secret_name, profile_name=None, region_name='ap-northeast-2'):
    response = client('secretsmanager', profile_name,
                      region_name).get_secret_value(SecretId=secret_name)
    return json.loads(response.get('SecretString') or '{}')


def ensure_secret(secret_name, profile_name=None, region_name='ap-northeast-2'):
    secretsmanager = client('secretsmanager', profile_name, region_name)
    try:
        secretsmanager.describe_secret(SecretId=secret_name)
        return False
    except secretsmanager.exceptions.ResourceNotFoundException:
        secretsmanager.create_secret(Name=secret_name, SecretString='{}')
        return True


def update_secret_values(secret_name, values, profile_name=None,
                         region_name='ap-northeast-2'):
    ensure_secret(secret_name, profile_name, region_name)
    current = secret_values(secret_name, profile_name, region_name)
    current.update(values)
    client('secretsmanager', profile_name, region_name).put_secret_value(
        SecretId=secret_name,
        SecretString=json.dumps(current, ensure_ascii=False),
    )
    return current


def rds_instance(db_identifier, profile_name=None, region_name='ap-northeast-2'):
    response = client('rds', profile_name, region_name).describe_db_instances(
        DBInstanceIdentifier=db_identifier
    )
    return response['DBInstances'][0]
