import os
from pathlib import Path
import shlex
import subprocess
import sys

sys.path.append(Path(__file__).parent.as_posix())

from conf import Conf
from djangox.deploy.aws import running_instances
from djangox.deploy.aws import tag_value


def ssh_env():
    env = os.environ.copy()
    if Conf.aws_profile:
        env['AWS_PROFILE'] = Conf.aws_profile
    env['AWS_DEFAULT_REGION'] = Conf.aws_region
    return env


def ssh_command(server):
    host, options = server
    return [
        'ssh',
        '-F',
        options['ssh_config_file'],
        '-i',
        str(Path(options['ssh_key']).expanduser()),
        '-o',
        'IdentitiesOnly=yes',
        f"{options['ssh_user']}@{host}",
    ]


def print_servers():
    for index, server in enumerate(servers):
        host, options = server
        print(f"{index}: {options['instance_name']} {options['instance_id']}")
        print(shlex.join(ssh_command(server)))


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


instances = sorted(
    running_instances(Conf.instance_tag_value, Conf.aws_profile,
                      Conf.aws_region, Conf.instance_tag_name),
    key=lambda instance: (tag_value(instance, 'Name'), instance['InstanceId']),
)

servers = [
    (instance['InstanceId'], {
        'ssh_user': Conf.ssh_user,
        'ssh_key': Conf.ssh_key,
        'ssh_config_file': str(Conf.ssh_config_path),
        'ssh_connect_retries': 20,
        'ssh_connect_retry_min_delay': 3,
        'ssh_connect_retry_max_delay': 10,
        'instance_id': instance['InstanceId'],
        'instance_name': tag_value(instance, 'Name'),
    })
    for instance in instances
]

if not servers:
    raise ValueError(
        f'No running EC2 instance found with {Conf.instance_tag_name}={Conf.instance_tag_value}'
    )


if __name__ == '__main__':
    server = select_server(sys.argv[1] if len(sys.argv) > 1 else None)
    if server:
        command = ssh_command(server)
        print(shlex.join(command))
        raise SystemExit(subprocess.run(command, env=ssh_env()).returncode)
