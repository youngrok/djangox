from pathlib import Path

import boto3

from conf import Conf


def ec2_client():
    if Conf.aws_profile:
        session = boto3.session.Session(profile_name=Conf.aws_profile, region_name=Conf.aws_region)
    else:
        session = boto3.session.Session(region_name=Conf.aws_region)
    return session.client('ec2')


def tag_value(instance, name):
    for tag in instance.get('Tags', []):
        if tag.get('Key') == name:
            return tag.get('Value', '')
    return ''


def running_instances():
    response = ec2_client().describe_instances(
        Filters=[
            {'Name': f'tag:{Conf.instance_tag_name}', 'Values': [Conf.instance_tag_value]},
            {'Name': 'instance-state-name', 'Values': ['running']},
        ]
    )
    return [
        instance
        for reservation in response['Reservations']
        for instance in reservation['Instances']
        if instance.get('PublicDnsName')
    ]


servers = [
    (instance['PublicDnsName'], {
        'ssh_user': Conf.ssh_user,
        'ssh_key': Conf.ssh_key,
        'instance_id': instance['InstanceId'],
        'instance_name': tag_value(instance, 'Name'),
    })
    for instance in running_instances()
]

if not servers:
    raise ValueError(
        f'No running EC2 instance found with {Conf.instance_tag_name}={Conf.instance_tag_value}'
    )


if __name__ == '__main__':
    for host, options in servers:
        key_path = Path(options['ssh_key']).expanduser()
        print(f"ssh -i {key_path} {options['ssh_user']}@{host}")
