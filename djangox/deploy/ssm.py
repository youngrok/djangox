import re
import shlex
import subprocess
from pathlib import Path

from djangox.deploy.aws import running_instances
from djangox.deploy.aws import send_shell_command
from djangox.deploy.aws import tag_value
from djangox.deploy.aws import wait_command


def deploy(Conf):
    instances = target_instances(Conf)
    command_id = send_shell_command(
        [instance['InstanceId'] for instance in instances],
        [server_script(Conf)],
        Conf.aws_profile,
        Conf.aws_region,
        f'{Conf.project_name} deploy',
    )
    results = wait_command(command_id,
                           [instance['InstanceId'] for instance in instances],
                           Conf.aws_profile,
                           Conf.aws_region)
    failed = False
    for instance in instances:
        result = results[instance['InstanceId']]
        if result.get('StandardOutputContent'):
            print(result['StandardOutputContent'])
        if result.get('StandardErrorContent'):
            print(result['StandardErrorContent'])
        if result['Status'] != 'Success':
            failed = True
    if failed:
        raise SystemExit(1)


def connect(Conf, target=''):
    instance = select_instance(Conf, target)
    command = ['aws', 'ssm', 'start-session',
               '--target', instance['InstanceId'],
               '--region', Conf.aws_region]
    if Conf.aws_profile:
        command.extend(['--profile', Conf.aws_profile])
    subprocess.run(command, check=True)


def list_instances(Conf):
    for index, instance in enumerate(target_instances(Conf)):
        name = tag_value(instance, 'Name')
        print(f"{index}: {name} {instance['InstanceId']}")
        print(f'./control.py connect --target {index}')


def select_instance(Conf, target=''):
    instances = target_instances(Conf)
    if not target and len(instances) == 1:
        return instances[0]
    if not target or target in ['list', 'servers']:
        list_instances(Conf)
        raise SystemExit(0)
    for index, instance in enumerate(instances):
        if target in [str(index), instance['InstanceId'], tag_value(instance, 'Name')]:
            return instance
    raise ValueError(f'No running EC2 instance found for {target}')


def target_instances(Conf):
    instances = sorted(
        running_instances(Conf.instance_tag_value, Conf.aws_profile,
                          Conf.aws_region, Conf.instance_tag_name),
        key=lambda instance: (tag_value(instance, 'Name'), instance['InstanceId']),
    )
    if not instances:
        raise ValueError(
            f'No running EC2 instance found with {Conf.instance_tag_name}={Conf.instance_tag_value}'
        )
    return instances


def server_script(Conf):
    context = Conf.template_vars()
    secret_files = getattr(Conf, 'secret_files', {
        'GITHUB_DEPLOY_KEY': Conf.github_deploy_key_path,
    })
    return f"""#!/bin/bash
set -euo pipefail

export AWS_DEFAULT_REGION={shlex.quote(Conf.aws_region)}
PROJECT_NAME={shlex.quote(Conf.project_name)}
ENVIRONMENT={shlex.quote(Conf.environment)}
COMMON_SECRET_NAME={shlex.quote(Conf.common_secret_name)}
SECRET_NAME={shlex.quote(Conf.secret_name)}
DB_IDENTIFIER={shlex.quote(Conf.db_identifier)}
HOME_DIR={shlex.quote(Conf.home)}
SSH_USER={shlex.quote(Conf.ssh_user)}

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y curl ca-certificates gnupg python3 python3-dev python3-venv git nginx nodejs postgresql-client build-essential fonts-nanum acl awscli
if ! command -v node >/dev/null || ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 20 ? 0 : 1)'; then
    apt-get remove -y libnode-dev nodejs-doc npm || true
    apt-get install -f -y
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
fi

mkdir -p "$HOME_DIR/.ssh" "$HOME_DIR/bin"
chown -R "$SSH_USER:$SSH_USER" "$HOME_DIR/.ssh" "$HOME_DIR/bin"
chmod 700 "$HOME_DIR/.ssh"
setfacl -m u:www-data:--x "$HOME_DIR"

python3 - <<'PY'
import json
import os
import subprocess
from pathlib import Path

common_secret_name = os.environ['COMMON_SECRET_NAME']
secret_name = os.environ['SECRET_NAME']
db_identifier = os.environ['DB_IDENTIFIER']
project_name = os.environ['PROJECT_NAME']
home = Path(os.environ['HOME_DIR'])
ssh_user = os.environ['SSH_USER']

def aws(args):
    return subprocess.check_output(['aws', *args], text=True).strip()

def secret_values(secret_id):
    return json.loads(aws([
        'secretsmanager',
        'get-secret-value',
        '--secret-id',
        secret_id,
        '--query',
        'SecretString',
        '--output',
        'text',
    ]))

values = secret_values(common_secret_name)
values.update(secret_values(secret_name))
db = json.loads(aws([
    'rds',
    'describe-db-instances',
    '--db-instance-identifier',
    db_identifier,
]))['DBInstances'][0]
db_secret = secret_values(db['MasterUserSecret']['SecretArn'])
values.update({{
    'DATABASE_NAME': project_name,
    'DATABASE_USER': db_secret['username'],
    'DATABASE_PASSWORD': db_secret['password'],
    'DATABASE_HOST': db['Endpoint']['Address'],
    'DATABASE_PORT': str(db['Endpoint']['Port']),
}})

for key, path in {secret_files!r}.items():
    Path(path).write_text(values[key], encoding='utf-8')
    Path(path).chmod(0o400)
    subprocess.run(['chown', f'{{ssh_user}}:{{ssh_user}}', path], check=True)

secret_settings = Path(f'/tmp/{{project_name}}-secret_settings.py')
secret_settings.write_text(
    ''.join(f'{{key}} = {{value!r}}\\n' for key, value in values.items()),
    encoding='utf-8',
)
secret_settings.chmod(0o600)
subprocess.run(['chown', f'{{ssh_user}}:{{ssh_user}}', secret_settings.as_posix()], check=True)
PY

cat > /tmp/$PROJECT_NAME-production.py <<'EOF'
{render_file(Conf.deploy_dir / 'production.py.j2', context)}
EOF
chown "$SSH_USER:$SSH_USER" /tmp/$PROJECT_NAME-production.py
chmod 600 /tmp/$PROJECT_NAME-production.py

install -o "$SSH_USER" -g "$SSH_USER" -m 744 /dev/stdin "$HOME_DIR/bin/loadenv" <<'EOF'
{render_file(Conf.deploy_dir / 'bin' / 'loadenv', context)}
EOF
install -o "$SSH_USER" -g "$SSH_USER" -m 744 /dev/stdin "$HOME_DIR/bin/djangorc" <<'EOF'
{render_file(Conf.deploy_dir / 'bin' / 'djangorc', context)}
EOF
install -o "$SSH_USER" -g "$SSH_USER" -m 744 /dev/stdin "$HOME_DIR/bin/deploy-release" <<'EOF'
{render_file(Conf.deploy_dir / 'bin' / 'deploy-release', context)}
EOF
install -o root -g root -m 644 /dev/stdin /etc/nginx/sites-available/{Conf.server_name} <<'EOF'
{render_file(Conf.deploy_dir / 'nginx-site.conf', context)}
EOF
ln -sfn /etc/nginx/sites-available/{Conf.server_name} /etc/nginx/sites-enabled/{Conf.server_name}
rm -f /etc/nginx/sites-enabled/default
install -o root -g root -m 644 /dev/stdin /etc/systemd/system/gunicorn.service <<'EOF'
{render_file(Conf.deploy_dir / 'gunicorn.service', context)}
EOF

systemctl daemon-reload
nginx -t
systemctl reload nginx || systemctl start nginx

sudo -u "$SSH_USER" SECRET_SETTINGS_SOURCE=/tmp/$PROJECT_NAME-secret_settings.py PRODUCTION_SETTINGS_SOURCE=/tmp/$PROJECT_NAME-production.py "$HOME_DIR/bin/deploy-release"
"""


def render_file(path, values):
    return re.sub(
        r'\{\{\s*([a-z_]+)\s*\}\}',
        lambda match: str(values.get(match.group(1), match.group(0))),
        Path(path).read_text(encoding='utf-8'),
    )
