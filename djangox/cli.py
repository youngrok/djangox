from enum import Enum
from typing import Optional

import typer
from django.core.management.utils import get_random_secret_key

from djangox.deploy.scaffold import check_prerequisites
from djangox.deploy.scaffold import setup_project
from djangox.secrets import create_secret
from djangox.secrets import get_secrets
from djangox.secrets import secret_console_url
from djangox.secrets import secrets_console_url
from djangox.secrets import write_secret_settings


app = typer.Typer(no_args_is_help=True)
secrets_app = typer.Typer(no_args_is_help=True)
deploy_app = typer.Typer(no_args_is_help=True)
app.add_typer(secrets_app, name='secrets')
app.add_typer(deploy_app, name='deploy')


class Environment(str, Enum):
    dev = 'dev'
    production = 'production'


@app.command('init')
def project_init(domain: str = typer.Option(..., '--domain', prompt=True),
                 aws_profile: str = typer.Option(..., '--aws-profile',
                                                  prompt=True),
                 aws_region: str = 'ap-northeast-2',
                 force: bool = False,
                 skip_checks: bool = False):
    if not skip_checks:
        try:
            check_prerequisites(aws_profile)
        except ValueError as error:
            typer.secho(str(error), fg=typer.colors.RED)
            raise typer.Exit(1)

    run_project_setup(domain, aws_profile, aws_region=aws_region, force=force)


@app.command('setup')
def project_setup(server_name: str = typer.Option(..., '--server-name'),
                  aws_profile: str = typer.Option(..., '--aws-profile'),
                  project_name: str = '',
                  repo: str = '',
                  static_dir: str = '',
                  settings_package: str = '',
                  deploy_dir: str = 'deploy',
                  djangox_repo: str = 'git@github.com:youngrok/djangox.git',
                  aws_region: str = 'ap-northeast-2',
                  storage_bucket_name: str = '',
                  force: bool = False):
    run_project_setup(server_name, aws_profile, project_name, repo, static_dir,
                      settings_package, deploy_dir, djangox_repo, aws_region,
                      storage_bucket_name, force)


def run_project_setup(server_name, aws_profile, project_name='', repo='',
                      static_dir='', settings_package='', deploy_dir='deploy',
                      djangox_repo='git@github.com:youngrok/djangox.git',
                      aws_region='ap-northeast-2', storage_bucket_name='',
                      force=False):
    try:
        result = setup_project(server_name, aws_profile, project_name, repo,
                               static_dir, settings_package, deploy_dir,
                               djangox_repo, aws_region, storage_bucket_name,
                               force)
    except (FileExistsError, ValueError) as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(1)

    print_setup_result(result)


@secrets_app.command()
def setup(project_name: str,
          env: Optional[list[Environment]] = typer.Option(None),
          region: str = 'ap-northeast-2',
          aws_profile: Optional[str] = typer.Option(None, '--aws-profile',
                                                    '--profile',
                                                    envvar='AWS_PROFILE',
                                                    help='AWS profile name.'),
          key: Optional[list[str]] = typer.Option(None, '--key'),
          generate: Optional[list[str]] = typer.Option(None, '--generate'),
          settings_package: Optional[str] = None,
          local_only: bool = False):
    if local_only and not (key or generate):
        typer.secho('Pass at least one --key or --generate option.',
                    fg=typer.colors.RED)
        raise typer.Exit(1)
    if not local_only and (key or generate):
        typer.secho('Use --key and --generate only with --local-only.',
                    fg=typer.colors.RED)
        raise typer.Exit(1)

    if not local_only:
        typer.secho('AWS Secrets Manager secrets:', fg=typer.colors.BLUE,
                    bold=True)
        for target_env in env or list(Environment):
            name = secret_name(project_name, target_env)
            if create_secret(name, region_name=region, profile_name=aws_profile):
                typer.secho(f'- {name}: created', fg=typer.colors.GREEN)
            else:
                typer.secho(f'- {name}: already exists',
                            fg=typer.colors.YELLOW)
            typer.secho(f'  open: {secret_console_url(name, region)}',
                        fg=typer.colors.CYAN)
        return

    local_values = {}
    for target_env in env or [Environment.dev]:
        name = secret_name(project_name, target_env)
        local_values = secret_values(name, key or [], generate or [])

    local_path = local_secret_settings_path(project_name, settings_package)
    write_secret_settings(local_path, local_values)

    typer.secho('Wrote local settings:', fg=typer.colors.GREEN)
    typer.echo(local_path)


@secrets_app.command()
def check(project_name: str,
          env: Optional[list[Environment]] = typer.Option(None),
          region: str = 'ap-northeast-2',
          aws_profile: Optional[str] = typer.Option(None, '--aws-profile',
                                                    '--profile',
                                                    envvar='AWS_PROFILE',
                                                    help='AWS profile name.'),
          key: Optional[list[str]] = typer.Option(None, '--key')):
    if not key:
        typer.secho('Pass at least one --key option.', fg=typer.colors.RED)
        raise typer.Exit(1)

    success = True
    for target_env in env or list(Environment):
        name = secret_name(project_name, target_env)
        missing = missing_keys(get_secrets(name, region, aws_profile), key)
        if missing:
            success = False
            typer.secho(f'{name}: missing {", ".join(missing)}',
                        fg=typer.colors.RED)
        else:
            typer.secho(f'{name}: ok', fg=typer.colors.GREEN)

    typer.echo()
    typer.secho('Open AWS Console:', fg=typer.colors.BLUE, bold=True)
    typer.secho(secrets_console_url(project_name, region),
                fg=typer.colors.CYAN)
    if not success:
        raise typer.Exit(1)


@deploy_app.command('setup')
def deploy_setup(server_name: str = typer.Option(..., '--server-name'),
                 aws_profile: str = typer.Option(..., '--aws-profile'),
                 project_name: str = '',
                 repo: str = '',
                 static_dir: str = '',
                 settings_package: str = '',
                 deploy_dir: str = 'deploy',
                 djangox_repo: str = 'git@github.com:youngrok/djangox.git',
                 aws_region: str = 'ap-northeast-2',
                 storage_bucket_name: str = '',
                 force: bool = False):
    run_project_setup(server_name, aws_profile, project_name, repo, static_dir,
                      settings_package, deploy_dir, djangox_repo, aws_region,
                      storage_bucket_name, force)


def secret_values(name, keys, generated_keys):
    values = {key: generate_secret_value() for key in generated_keys}
    for key in keys:
        values[key] = typer.prompt(f'{name} {key}')
    return values


def print_setup_result(result):
    if result['created']:
        typer.secho('Created:', fg=typer.colors.GREEN)
        for path in result['created']:
            typer.echo(path)
    if result['updated']:
        typer.secho('Updated:', fg=typer.colors.BLUE)
        for path in result['updated']:
            typer.echo(path)
    if result['modified']:
        typer.secho('Modified files kept:', fg=typer.colors.YELLOW)
        for path in result['modified']:
            typer.echo(f'{path} differs from the template, so it was not overwritten.')
    if not result['created'] and not result['updated'] and not result['modified']:
        typer.secho('No changes.', fg=typer.colors.GREEN)


def missing_keys(values, keys):
    return [key for key in keys if not values.get(key)]


def secret_name(project_name, env):
    return f'{project_name}-keys-{env.value}'


def local_secret_settings_path(project_name, settings_package=None):
    package = settings_package or project_name.replace('-', '_')
    return f'{package}/secret_settings.py'


def generate_secret_value():
    return get_random_secret_key()


def main():
    app()
