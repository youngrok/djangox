from io import StringIO
from pathlib import Path
import sys

from pyinfra import config
from pyinfra.operations import apt, files, server, systemd

sys.path.append(Path(__file__).parent.as_posix())

from djangox.secrets import dict_to_python_code
from djangox.secrets import get_secrets
from conf import Conf

secrets = get_secrets(Conf.secret_name, Conf.aws_region, Conf.aws_profile)

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
    ],
    _sudo=True,
)

files.directory(f'{Conf.home}/.ssh', mode='700')
files.directory(f'{Conf.home}/bin')
files.directory(Conf.shared_path)

files.put(StringIO(secrets['GITHUB_DEPLOY_KEY']), Conf.github_deploy_key_path,
          mode='400')
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
    f'{Conf.shared_path}/secret_settings.py',
    mode='600',
)
files.template(
    src=str(Conf.deploy_dir / 'production.py.j2'),
    dest=f'{Conf.shared_path}/production.py',
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
server.shell(commands=[f'{Conf.home}/bin/deploy-release'])
