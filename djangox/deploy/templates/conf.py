import os
from pathlib import Path


class Conf:
    deploy_dir = Path(__file__).parent.absolute()

    project_name = {{ project_name_py }}
    settings_package = {{ settings_package_py }}
    environment = os.getenv('DJANGOX_ENVIRONMENT', 'production')
    aws_profile = os.getenv('AWS_PROFILE')
    aws_region = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or {{ aws_region_py }}
    common_secret_name = f'{project_name}-keys-dev'
    secret_name = f'{project_name}-keys-{environment}'

    ssh_user = 'ubuntu'
    instance_tag_name = 'project'
    instance_tag_value = project_name
    instance_type = 't3.micro'
    ubuntu_ami_name = 'ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*'

    home = f'/home/{ssh_user}'
    current_path = f'{home}/{project_name}'
    project_repo = {{ repo_py }}
    djangox_repo = {{ djangox_repo_py }}
    branch = 'main'

    github_deploy_key_path = f'{home}/.ssh/id_deploy'
    secret_files = {'GITHUB_DEPLOY_KEY': github_deploy_key_path}
    git_ssh_command = f'ssh -i {github_deploy_key_path} -o IdentitiesOnly=yes -o StrictHostKeyChecking=no'

    server_name = {{ server_name_py }}
    static_path = f'{home}/static'
    static_dir = {{ static_dir_py }}
    network = {{ network_py }}
    vpc_name = ''
    gunicorn_processes = 3
    gunicorn_port = 8000
    health_path = '/health/'
    keep_releases = 2
    storage_bucket_name = {{ storage_bucket_name_py }}

    db_name = project_name
    db_identifier = project_name
    db_username = project_name
    rds_instance_class = 'db.t4g.micro'
    redis_node_type = 'cache.t4g.micro'
    deletion_protection = True

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
