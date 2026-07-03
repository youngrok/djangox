import os
from pathlib import Path


class Conf:
    deploy_dir = Path(__file__).parent.absolute()

    project_name = {{ project_name_py }}
    settings_package = {{ settings_package_py }}
    environment = 'production'
    aws_profile = os.getenv('AWS_PROFILE')
    aws_region = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or {{ aws_region_py }}
    secret_name = f'keys-{project_name}-{environment}'

    ssh_user = 'ubuntu'
    ssh_key = str(Path({{ ssh_key_py }}).expanduser())
    instance_tag_name = 'project'
    instance_tag_value = project_name

    home = f'/home/{ssh_user}'
    current_path = f'{home}/{project_name}'
    shared_path = f'{home}/{project_name}-shared'
    release_glob = f'{home}/{project_name}-[0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]'
    static_glob = f'{home}/static-[0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]'
    project_dir = current_path
    project_repo = {{ repo_py }}
    djangox_dir = f'{home}/djangox'
    djangox_repo = {{ djangox_repo_py }}
    branch = 'main'

    github_deploy_key_path = f'{home}/.ssh/id_deploy'
    git_ssh_command = f'ssh -i {github_deploy_key_path} -o IdentitiesOnly=yes -o StrictHostKeyChecking=no'

    server_name = {{ server_name_py }}
    server_alias = ''
    nginx_port = 80
    static_path = f'{home}/static'
    static_dir = {{ static_dir_py }}
    gunicorn_processes = 3
    gunicorn_port = 8000
    health_path = '/'
    keep_releases = 5
    storage_bucket_name = {{ storage_bucket_name_py }}

    allowed_hosts = [server_name]
    csrf_trusted_origins = [f'https://{server_name}']
    allowed_hosts_python = repr(allowed_hosts)
    csrf_trusted_origins_python = repr(csrf_trusted_origins)

    @classmethod
    def template_vars(cls):
        return {
            key: value
            for key, value in cls.__dict__.items()
            if not key.startswith('__') and key != 'template_vars' and not callable(value)
        }
