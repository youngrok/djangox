import atexit
import os
import shlex
import socket
import subprocess
import time

from djangox.deploy.aws import running_instances
from djangox.deploy.aws import tag_value
from djangox.deploy.aws import temporary_instance_connect_key


def ssm_port_forwarded_servers(Conf, open_tunnels=True):
    instances = sorted(
        running_instances(Conf.instance_tag_value, Conf.aws_profile,
                          Conf.aws_region, Conf.instance_tag_name),
        key=lambda instance: (tag_value(instance, 'Name'), instance['InstanceId']),
    )
    if not instances:
        raise ValueError(
            f'No running EC2 instance found with {Conf.instance_tag_name}={Conf.instance_tag_value}'
        )
    if not open_tunnels:
        return [(instance['InstanceId'], {
            'instance_id': instance['InstanceId'],
            'instance_name': tag_value(instance, 'Name'),
        }) for instance in instances]
    ssh_key = temporary_instance_connect_key(instances, Conf.ssh_user,
                                             Conf.aws_profile, Conf.aws_region)
    return [server_data(Conf, instance, ssh_key) for instance in instances]


def server_data(Conf, instance, ssh_key):
    port = free_port()
    start_port_forward(Conf, instance, port)
    return instance['InstanceId'], {
        'ssh_hostname': '127.0.0.1',
        'ssh_user': Conf.ssh_user,
        'ssh_port': port,
        'ssh_key': ssh_key,
        'ssh_known_hosts_file': '/dev/null',
        'ssh_strict_host_key_checking': 'no',
        'ssh_connect_retries': 20,
        'ssh_connect_retry_min_delay': 3,
        'ssh_connect_retry_max_delay': 10,
        'instance_id': instance['InstanceId'],
        'instance_name': tag_value(instance, 'Name'),
    }


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def start_port_forward(Conf, instance, port):
    command = [
        'aws',
        'ssm',
        'start-session',
        '--target',
        instance['InstanceId'],
        '--document-name',
        'AWS-StartPortForwardingSession',
        '--parameters',
        f'portNumber=22,localPortNumber={port}',
        '--region',
        Conf.aws_region,
    ]
    if Conf.aws_profile:
        command.extend(['--profile', Conf.aws_profile])
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, text=True,
                               env=aws_env(Conf))
    atexit.register(process.terminate)
    wait_for_port(port, process)


def wait_for_port(port, process):
    for _ in range(30):
        if process.poll() is not None:
            raise RuntimeError(
                f'SSM port forwarding exited: {process.stderr.read().strip()}'
            )
        with socket.socket() as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                return
        time.sleep(0.5)
    raise RuntimeError(f'SSM port forwarding did not open: {port}')


def connect(Conf, servers, target=None):
    server = select_server(servers, target)
    if not server:
        return 0
    command = ssh_command(server)
    print(shlex.join(command))
    return subprocess.run(command, env=aws_env(Conf)).returncode


def select_server(servers, target=None):
    if target is None and len(servers) == 1:
        return servers[0]
    if target is None or target in ['list', 'servers']:
        print_servers(servers)
        return None
    for index, server in enumerate(servers):
        name, options = server
        if target in [
            str(index),
            name,
            options['instance_id'],
            options['instance_name'],
        ]:
            return server
    raise ValueError(f'No running EC2 instance found for {target}')


def print_servers(servers):
    for index, (_, options) in enumerate(servers):
        print(f"{index}: {options['instance_name']} {options['instance_id']}")
        print(f'./control.py connect {index}')


def ssh_command(server):
    _, options = server
    return [
        'ssh',
        '-p',
        str(options['ssh_port']),
        '-i',
        options['ssh_key'],
        '-o',
        'IdentitiesOnly=yes',
        '-o',
        'StrictHostKeyChecking=no',
        '-o',
        'UserKnownHostsFile=/dev/null',
        f"{options['ssh_user']}@{options['ssh_hostname']}",
    ]


def aws_env(Conf):
    env = os.environ.copy()
    if Conf.aws_profile:
        env['AWS_PROFILE'] = Conf.aws_profile
    env['AWS_DEFAULT_REGION'] = Conf.aws_region
    return env
