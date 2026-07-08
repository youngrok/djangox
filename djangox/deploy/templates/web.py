from io import StringIO
from pathlib import Path
import sys

from pyinfra import config
from pyinfra.operations import apt, files, server, systemd

sys.path.append(Path(__file__).parent.as_posix())

from conf import Conf
from djangox.deploy.aws import rds_instance
from djangox.deploy.aws import secret_values
from djangox.secrets import dict_to_python_code


def deployment_secrets():
    values = secret_values(Conf.common_secret_name, Conf.aws_profile, Conf.aws_region)
    values.update(secret_values(Conf.secret_name, Conf.aws_profile, Conf.aws_region))
    db = rds_instance(Conf.db_identifier, Conf.aws_profile, Conf.aws_region)
    db_secret = secret_values(db['MasterUserSecret']['SecretArn'],
                              Conf.aws_profile, Conf.aws_region)
    values.update({
        'DATABASE_NAME': Conf.db_name,
        'DATABASE_USER': db_secret['username'],
        'DATABASE_PASSWORD': db_secret['password'],
        'DATABASE_HOST': db['Endpoint']['Address'],
        'DATABASE_PORT': str(db['Endpoint']['Port']),
    })
    return values


secrets = deployment_secrets()
secret_settings_path = f'/tmp/{Conf.project_name}-secret_settings.py'
production_settings_path = f'/tmp/{Conf.project_name}-production.py'

config.ENV = {'GIT_SSH_COMMAND': Conf.git_ssh_command}

apt.update(_sudo=True)
apt.packages(
    packages=[
        'curl',
        'ca-certificates',
        'gnupg',
    ],
    _sudo=True,
)
server.shell(
    commands=[
        "if command -v node >/dev/null && node -e 'process.exit(Number(process.versions.node.split(\".\")[0]) >= 20 ? 0 : 1)'; then exit 0; fi; apt-get remove -y libnode-dev nodejs-doc npm || true; apt-get install -f -y; curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs",
    ],
    _sudo=True,
)
apt.packages(
    packages=[
        'python3',
        'python3-dev',
        'python3-venv',
        'git',
        'nginx',
        'nodejs',
        'postgresql-client',
        'build-essential',
        'fonts-nanum',
        'acl',
    ],
    _sudo=True,
)

files.directory(f'{Conf.home}/.ssh', mode='700')
files.directory(f'{Conf.home}/bin')
server.shell(commands=[f'setfacl -m u:www-data:--x {Conf.home}'], _sudo=True)

for key, path in Conf.secret_files.items():
    files.put(StringIO(secrets[key]), path, mode='400')

files.put(str(Conf.deploy_dir / 'bin' / 'loadenv'), f'{Conf.home}/bin/loadenv')
files.file(f'{Conf.home}/bin/loadenv', mode='744')
files.template(
    src=str(Conf.deploy_dir / 'bin' / 'djangorc'),
    dest=f'{Conf.home}/bin/djangorc',
    mode='744',
    **Conf.template_vars(),
)
files.template(
    src=str(Conf.deploy_dir / 'bin' / 'deploy-release'),
    dest=f'{Conf.home}/bin/deploy-release',
    mode='744',
    **Conf.template_vars(),
)

files.put(
    StringIO(dict_to_python_code(secrets)),
    secret_settings_path,
    mode='600',
)
files.template(
    src=str(Conf.deploy_dir / 'production.py.j2'),
    dest=production_settings_path,
    mode='600',
    **Conf.template_vars(),
)

files.template(
    src=str(Conf.deploy_dir / 'nginx-site.conf'),
    dest=f'/etc/nginx/sites-available/{Conf.server_name}',
    mode='644',
    _sudo=True,
    **Conf.template_vars(),
)
files.link(
    path=f'/etc/nginx/sites-enabled/{Conf.server_name}',
    target=f'/etc/nginx/sites-available/{Conf.server_name}',
    _sudo=True,
)
files.link('/etc/nginx/sites-enabled/default', present=False, _sudo=True)

files.template(
    src=str(Conf.deploy_dir / 'gunicorn.service'),
    dest='/etc/systemd/system/gunicorn.service',
    _sudo=True,
    **Conf.template_vars(),
)

server.shell(commands=['systemctl daemon-reload'], _sudo=True)
server.shell(commands=['nginx -t'], _sudo=True)

systemd.service(service='nginx.service', reloaded=True, enabled=True, _sudo=True)
server.shell(commands=[
    f"trap 'rm -f {secret_settings_path} {production_settings_path}' EXIT; "
    f"SECRET_SETTINGS_SOURCE={secret_settings_path} "
    f"PRODUCTION_SETTINGS_SOURCE={production_settings_path} "
    f"{Conf.home}/bin/deploy-release"
])
