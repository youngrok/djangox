import os
from pathlib import Path
import shlex
import subprocess
import sys

sys.path.append(Path(__file__).parent.as_posix())

from conf import Conf
from djangox.deploy.aws import running_instances
from djangox.deploy.aws import tag_value
from djangox.deploy.aws import temporary_instance_connect_key


def ssh_env():
    env = os.environ.copy()
    if Conf.aws_profile:
        env['AWS_PROFILE'] = Conf.aws_profile
    env['AWS_DEFAULT_REGION'] = Conf.aws_region
    return env


def ssh_command(server):
    host, options = server
    command = [
        'ssh',
        '-F',
        options['ssh_config_file'],
    ]
    if options.get('ssh_key'):
        command.extend(['-i', options['ssh_key'], '-o', 'IdentitiesOnly=yes'])
    command.append(f"{options['ssh_user']}@{host}")
    return command


def print_servers():
    for index, (_, options) in enumerate(servers):
        print(f"{index}: {options['instance_name']} {options['instance_id']}")
        print(f'./control.py connect {index}')


def select_server(target=None):
    if target is None and len(servers) == 1:
        return servers[0]
    if target is None or target in ['list', 'servers']:
        print_servers()
        return None
    for index, server in enumerate(servers):
        host, options = server
        if target in [str(index), host, options['instance_id'], options['instance_name']]:
            return server
    raise ValueError(f'No running EC2 instance found for {target}')


def should_authorize_instance_connect():
    if __name__ != '__main__':
        return True
    return len(sys.argv) == 1 or sys.argv[1] not in ['list', 'servers']


def server_data(instance):
    data = {
        'ssh_user': Conf.ssh_user,
        'ssh_config_file': str(Conf.ssh_config_path),
        'ssh_connect_retries': 20,
        'ssh_connect_retry_min_delay': 3,
        'ssh_connect_retry_max_delay': 10,
        'instance_id': instance['InstanceId'],
        'instance_name': tag_value(instance, 'Name'),
    }
    if ssh_key:
        data['ssh_key'] = ssh_key
    return data


instances = sorted(
    running_instances(Conf.instance_tag_value, Conf.aws_profile,
                      Conf.aws_region, Conf.instance_tag_name),
    key=lambda instance: (tag_value(instance, 'Name'), instance['InstanceId']),
)

if not instances:
    raise ValueError(
        f'No running EC2 instance found with {Conf.instance_tag_name}={Conf.instance_tag_value}'
    )

ssh_key = None
if should_authorize_instance_connect():
    ssh_key = temporary_instance_connect_key(instances, Conf.ssh_user,
                                             Conf.aws_profile, Conf.aws_region)

servers = [
    (instance['InstanceId'], server_data(instance))
    for instance in instances
]


if __name__ == '__main__':
    server = select_server(sys.argv[1] if len(sys.argv) > 1 else None)
    if server:
        command = ssh_command(server)
        print(shlex.join(command))
        raise SystemExit(subprocess.run(command, env=ssh_env()).returncode)
