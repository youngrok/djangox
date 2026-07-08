from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from djangox.deploy.ssm import server_script


class Conf:
    project_name = 'perspective'
    settings_package = 'perspective'
    environment = 'production'
    aws_profile = 'ecolemo'
    aws_region = 'ap-northeast-2'
    common_secret_name = 'perspective-keys-dev'
    secret_name = 'perspective-keys-production'
    deploy_dir = None
    ssh_user = 'ubuntu'
    home = '/home/ubuntu'
    db_identifier = 'perspective'
    github_deploy_key_path = '/home/ubuntu/.ssh/id_deploy'
    secret_files = {'GITHUB_DEPLOY_KEY': github_deploy_key_path}
    server_name = 'example.com'
    static_path = '/home/ubuntu/static'
    current_path = '/home/ubuntu/perspective'
    project_repo = 'git@github.com:youngrok/perspective.git'
    djangox_repo = 'git@github.com:youngrok/djangox.git'
    branch = 'main'
    static_dir = 'wiki/static'
    gunicorn_processes = 3
    gunicorn_port = 8000
    health_path = '/'
    keep_releases = 2
    storage_bucket_name = 'perspective'
    allowed_hosts_python = "['example.com']"
    csrf_trusted_origins_python = "['https://example.com']"

    @classmethod
    def template_vars(cls):
        return {
            key: value
            for key, value in cls.__dict__.items()
            if not key.startswith('__') and key != 'template_vars' and not callable(value)
        }


class DeploySsmTest(TestCase):
    def test_server_script_reads_secrets_on_instance(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            Conf.deploy_dir = root
            (root / 'bin').mkdir()
            (root / 'bin' / 'loadenv').write_text('loadenv')
            (root / 'bin' / 'djangorc').write_text('djangorc')
            (root / 'bin' / 'deploy-release').write_text('deploy-release')
            (root / 'nginx-site.conf').write_text('server {{ server_name }}')
            (root / 'gunicorn.service').write_text('gunicorn {{ current_path }}')
            (root / 'production.py.j2').write_text(
                'ALLOWED_HOSTS = {{ allowed_hosts_python }}')

            script = server_script(Conf)

        self.assertIn("'secretsmanager'", script)
        self.assertIn("'get-secret-value'", script)
        self.assertIn("'rds'", script)
        self.assertIn("'describe-db-instances'", script)
        self.assertIn("'GITHUB_DEPLOY_KEY': '/home/ubuntu/.ssh/id_deploy'",
                      script)
        self.assertIn("ALLOWED_HOSTS = ['example.com']", script)
        self.assertIn('sudo -u "$SSH_USER"', script)
        self.assertNotIn('pyinfra', script)
        self.assertNotIn('SECRET_SETTINGS_SOURCE:?', script)
