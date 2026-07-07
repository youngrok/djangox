import os
from pathlib import Path
import subprocess
import sys
import tempfile

import typer

from djangox.deploy.aws import ensure_secret
from djangox.deploy.aws import secret_values
from djangox.deploy.aws import update_secret_values
from djangox.secrets import secret_console_url


app = typer.Typer(no_args_is_help=True)
infra_app = typer.Typer(invoke_without_command=True)
app.add_typer(infra_app, name='infra')
EXCLUDED_MODULES = {'__init__', 'conf', 'infra', 'web'}


@infra_app.callback(invoke_without_command=True)
def infra(ctx: typer.Context):
    if ctx.invoked_subcommand:
        return
    for environment in environments():
        typer.echo(environment)


@infra_app.command('add')
def infra_add(environment: str):
    Conf = load_conf(environment)
    for name in secret_names(Conf, environment):
        if ensure_secret(name, Conf.aws_profile, Conf.aws_region):
            typer.secho(f'{name}: created', fg=typer.colors.GREEN)
        else:
            typer.secho(f'{name}: already exists', fg=typer.colors.YELLOW)
        typer.secho(secret_console_url(name, Conf.aws_region),
                    fg=typer.colors.CYAN)
    ensure_deploy_key(Conf)


@infra_app.command('setup')
def infra_setup(environment: str):
    Conf = load_conf(environment)
    infra_add(environment)
    run(['npx', 'aws-cdk', 'deploy', f'{Conf.project_name}-{environment}'],
        cwd=Path('deploy'), env=command_env(Conf, environment))


@app.command()
def deploy(environment: str):
    Conf = load_conf(environment)
    run(['pyinfra', f'deploy/{environment}.py', 'deploy/web.py'],
        env=command_env(Conf, environment))


@app.command()
def connect(target: str = '', environment: str = 'production'):
    Conf = load_conf(environment)
    command = [sys.executable, f'deploy/{environment}.py']
    if target:
        command.append(target)
    run(command, env=command_env(Conf, environment))


def environments():
    return [
        path.stem
        for path in sorted(Path('deploy').glob('*.py'))
        if path.stem not in EXCLUDED_MODULES
    ]


def load_conf(environment):
    if environment not in environments():
        raise typer.BadParameter(f'No deploy environment: {environment}')
    os.environ['DJANGOX_ENVIRONMENT'] = environment
    sys.modules.pop('conf', None)
    deploy_path = Path('deploy').resolve().as_posix()
    if deploy_path not in sys.path:
        sys.path.insert(0, deploy_path)
    from conf import Conf
    return Conf


def secret_names(Conf, environment):
    names = [Conf.common_secret_name]
    if environment != 'dev':
        names.append(Conf.secret_name)
    return names


def ensure_deploy_key(Conf):
    repo = github_repo(Conf.project_repo)
    current = secret_values(Conf.common_secret_name, Conf.aws_profile,
                            Conf.aws_region)
    if current.get('GITHUB_DEPLOY_KEY') and deploy_key_exists(repo, Conf.project_name):
        typer.secho('GitHub deploy key: already exists', fg=typer.colors.YELLOW)
        return

    with tempfile.TemporaryDirectory() as directory:
        key_path = Path(directory) / 'id_ed25519'
        run(['ssh-keygen', '-t', 'ed25519', '-N', '', '-C',
             f'{Conf.project_name}-deploy', '-f', key_path.as_posix(), '-q'])
        run(['gh', 'repo', 'deploy-key', 'add', f'{key_path}.pub',
             '--repo', repo, '--title', Conf.project_name])
        update_secret_values(Conf.common_secret_name, {
            'GITHUB_DEPLOY_KEY': key_path.read_text(encoding='utf-8'),
        }, Conf.aws_profile, Conf.aws_region)
    typer.secho('GitHub deploy key: created', fg=typer.colors.GREEN)


def github_repo(repo_url):
    if repo_url.startswith('git@github.com:'):
        return repo_url.removeprefix('git@github.com:').removesuffix('.git')
    if repo_url.startswith('https://github.com/'):
        return repo_url.removeprefix('https://github.com/').removesuffix('.git')
    raise ValueError(f'Unsupported GitHub repo URL: {repo_url}')


def deploy_key_exists(repo, title):
    result = subprocess.run(['gh', 'repo', 'deploy-key', 'list',
                             '--repo', repo, '--json', 'title'],
                            text=True, capture_output=True)
    return result.returncode == 0 and f'"{title}"' in result.stdout


def command_env(Conf, environment):
    env = os.environ.copy()
    env['DJANGOX_ENVIRONMENT'] = environment
    env['AWS_DEFAULT_REGION'] = Conf.aws_region
    if Conf.aws_profile:
        env['AWS_PROFILE'] = Conf.aws_profile
    return env


def run(command, cwd=None, env=None):
    typer.echo(' '.join(command))
    subprocess.run(command, cwd=cwd, env=env, check=True)
