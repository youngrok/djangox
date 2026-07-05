import os
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from typer.testing import CliRunner

from djangox.cli import app


class DjangoxCliTest(TestCase):
    def prepare_project(self, temp_dir):
        root = Path(temp_dir)
        (root / 'manage.py').write_text(
            "import os\n"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'perspective.settings')\n")
        (root / 'perspective').mkdir()
        (root / 'perspective' / 'settings.py').write_text('')
        (root / 'wiki' / 'static').mkdir(parents=True)
        (root / 'wiki' / 'static' / 'package.json').write_text('{}')
        (root / '.envrc').write_text(
            '. .venv/bin/activate\n'
            'export AWS_PROFILE=old\n')
        subprocess.run(['git', 'init'], cwd=temp_dir, check=True,
                       capture_output=True)
        subprocess.run([
            'git', 'remote', 'add', 'origin',
            'git@github.com:youngrok/perspective.git'],
            cwd=temp_dir, check=True, capture_output=True)

    def test_secrets_setup_creates_dev_and_production_secrets(self):
        runner = CliRunner()

        with patch('djangox.cli.create_secret',
                   side_effect=[True, False]) as create_secret:
            result = runner.invoke(app, [
                'secrets', 'setup', 'perspective',
                '--aws-profile', 'work'], color=True)

        output = result.output

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(create_secret.call_args_list[0].args[0],
                         'keys-perspective-dev')
        self.assertEqual(create_secret.call_args_list[0].kwargs, {
            'region_name': 'ap-northeast-2',
            'profile_name': 'work',
        })
        self.assertEqual(create_secret.call_args_list[1].args[0],
                         'keys-perspective-production')
        self.assertIn('keys-perspective-dev: created', output)
        self.assertIn('keys-perspective-production: already exists', output)
        self.assertIn('\x1b[32m', output)
        self.assertIn('\x1b[33m', output)
        self.assertIn('\x1b[36m', output)
        self.assertNotIn('newsecret?region=ap-northeast-2', output)
        self.assertIn('home?region=ap-northeast-2#!/secret?name=keys-perspective-dev',
                      output)
        self.assertIn('home?region=ap-northeast-2#!/secret?name=keys-perspective-production',
                      output)
        self.assertNotIn('SERVICE_API_KEY', output)
        self.assertNotIn('perspective/secret_settings.py', output)
        self.assertNotIn('OAuth', output)
        self.assertNotIn(': :', output)

    def test_secrets_setup_can_write_local_settings_only(self):
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                with patch('djangox.cli.generate_secret_value',
                           return_value='dev-django-secret'):
                    result = runner.invoke(app, [
                        'secrets', 'setup', 'perspective',
                        '--local-only',
                        '--generate', 'SECRET_KEY',
                        '--key', 'SERVICE_API_KEY',
                        '--key', 'SERVICE_API_SECRET'],
                        input=(
                        'dev-client\n'
                        'dev-secret\n'))
            finally:
                os.chdir(cwd)

            path = Path(temp_dir) / 'perspective' / 'secret_settings.py'
            self.assertEqual(path.read_text(), (
                "SECRET_KEY = 'dev-django-secret'\n"
                "SERVICE_API_KEY = 'dev-client'\n"
                "SERVICE_API_SECRET = 'dev-secret'\n"))

        self.assertEqual(result.exit_code, 0)
        self.assertIn('Wrote local settings', result.output)

    def test_secrets_check_reports_missing_keys(self):
        runner = CliRunner()

        root_help = runner.invoke(app).output
        self.assertIn('setup', root_help)
        self.assertIn('secrets', root_help)
        secrets_help = runner.invoke(app, ['secrets']).output
        self.assertIn('setup', secrets_help)
        self.assertIn('check', secrets_help)

        with patch('djangox.cli.get_secrets',
                   return_value={'SECRET_KEY': 'secret'}) as get_secrets:
            result = runner.invoke(app, [
                'secrets', 'check', 'perspective', '--env', 'dev',
                '--aws-profile', 'work',
                '--key', 'SECRET_KEY',
                '--key', 'SERVICE_API_KEY'])

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(get_secrets.call_args.args[2], 'work')
        self.assertIn('missing', result.output)
        self.assertIn('SERVICE_API_KEY', result.output)

    def test_secrets_commands_require_explicit_keys(self):
        runner = CliRunner()

        setup_result = runner.invoke(app, [
            'secrets', 'setup', 'perspective', '--local-only'])
        setup_with_key_result = runner.invoke(app, [
            'secrets', 'setup', 'perspective', '--key', 'SERVICE_API_KEY'])
        check_result = runner.invoke(app, ['secrets', 'check', 'perspective'])

        self.assertEqual(setup_result.exit_code, 1)
        self.assertEqual(setup_with_key_result.exit_code, 1)
        self.assertEqual(check_result.exit_code, 1)
        self.assertIn('--key or --generate', setup_result.output)
        self.assertIn('only with --local-only', setup_with_key_result.output)
        self.assertIn('--key', check_result.output)

    def test_setup_writes_deploy_files_and_envrc(self):
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            self.prepare_project(temp_dir)
            cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                result = runner.invoke(app, [
                    'setup',
                    '--server-name', 'example.com',
                    '--aws-profile', 'ecolemo',
                    '--ssh-key', '~/.ssh/perspective.pem'])
            finally:
                os.chdir(cwd)

            deploy_dir = Path(temp_dir) / 'deploy'
            conf = deploy_dir / 'conf.py'
            web = deploy_dir / 'web.py'
            readme = deploy_dir / 'README.md'
            production = deploy_dir / 'production.py'

            self.assertEqual(result.exit_code, 0)
            self.assertIn('Created:', result.output)
            self.assertIn('Updated:', result.output)
            self.assertTrue(conf.exists())
            self.assertTrue(web.exists())
            self.assertTrue(production.exists())
            self.assertTrue((deploy_dir / 'ssh_config').exists())
            self.assertTrue((deploy_dir / 'bin' / 'loadenv').exists())
            self.assertTrue((deploy_dir / 'bin' / 'deploy-release').exists())
            self.assertTrue((deploy_dir / 'gunicorn.service').exists())
            self.assertIn("project_name = 'perspective'", conf.read_text())
            self.assertIn("settings_package = 'perspective'", conf.read_text())
            self.assertIn("git@github.com:youngrok/perspective.git",
                          conf.read_text())
            self.assertIn("server_name = 'example.com'", conf.read_text())
            self.assertIn("ssh_key = str(Path('~/.ssh/perspective.pem').expanduser())",
                          conf.read_text())
            self.assertIn("os.getenv('AWS_PROFILE')", conf.read_text())
            self.assertIn("os.getenv('AWS_REGION')", conf.read_text())
            self.assertNotIn("PERSPECTIVE_AWS_PROFILE", conf.read_text())
            self.assertNotIn("PERSPECTIVE_AWS_REGION", conf.read_text())
            self.assertNotIn("PERSPECTIVE_SERVER_NAME", conf.read_text())
            self.assertNotIn("PERSPECTIVE_SSH_KEY", conf.read_text())
            self.assertNotIn("PERSPECTIVE_AWS_PROFILE", readme.read_text())
            self.assertNotIn("PERSPECTIVE_AWS_REGION", readme.read_text())
            self.assertNotIn("PERSPECTIVE_SERVER_NAME", readme.read_text())
            self.assertIn('. .venv/bin/activate',
                          (Path(temp_dir) / '.envrc').read_text())
            self.assertIn('export AWS_PROFILE=ecolemo',
                          (Path(temp_dir) / '.envrc').read_text())
            self.assertNotIn('example.com',
                             (Path(temp_dir) / '.envrc').read_text())
            self.assertNotIn('perspective.pem',
                             (Path(temp_dir) / '.envrc').read_text())
            self.assertIn("current_path =", conf.read_text())
            self.assertIn("keep_releases =", conf.read_text())
            self.assertIn("static_dir = 'wiki/static'", conf.read_text())
            self.assertIn("deploy-release", web.read_text())
            self.assertFalse((deploy_dir / 'inventory.py').exists())
            self.assertIn("pyinfra deploy/production.py deploy/web.py",
                          readme.read_text())
            self.assertIn("python deploy/production.py", readme.read_text())
            self.assertIn("AWS_DEFAULT_REGION", production.read_text())
            self.assertIn("ln -sfn",
                          (deploy_dir / 'bin' / 'deploy-release').read_text())
            self.assertIn("STATIC_DIR=\"wiki/static\"",
                          (deploy_dir / 'bin' / 'deploy-release').read_text())
            self.assertIn("systemctl reload gunicorn.service",
                          (deploy_dir / 'bin' / 'deploy-release').read_text())
            self.assertIn("GITHUB_DEPLOY_KEY", readme.read_text())
            self.assertNotIn("deploy/id_deploy",
                             (Path(temp_dir) / '.gitignore').read_text())

    def test_setup_is_idempotent(self):
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            self.prepare_project(temp_dir)
            cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                first = runner.invoke(app, [
                    'setup',
                    '--server-name', 'example.com',
                    '--aws-profile', 'ecolemo',
                    '--ssh-key', '~/.ssh/perspective.pem'])
                second = runner.invoke(app, [
                    'setup',
                    '--server-name', 'example.com',
                    '--aws-profile', 'ecolemo',
                    '--ssh-key', '~/.ssh/perspective.pem'])
            finally:
                os.chdir(cwd)

            self.assertEqual(first.exit_code, 0)
            self.assertEqual(second.exit_code, 0)
            self.assertIn('No changes.', second.output)
            self.assertEqual(
                (Path(temp_dir) / '.gitignore').read_text().count('deploy/*.pem'),
                1,
            )
            self.assertEqual(
                (Path(temp_dir) / '.envrc').read_text().count('export AWS_PROFILE=ecolemo'),
                1,
            )

    def test_setup_keeps_modified_copied_files(self):
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            self.prepare_project(temp_dir)
            deploy_dir = Path(temp_dir) / 'deploy'
            deploy_dir.mkdir()
            (deploy_dir / 'conf.py').write_text('custom')
            cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                result = runner.invoke(app, [
                    'setup',
                    '--server-name', 'example.com',
                    '--aws-profile', 'ecolemo',
                    '--ssh-key', '~/.ssh/perspective.pem'])
            finally:
                os.chdir(cwd)

            self.assertEqual(result.exit_code, 0)
            self.assertEqual((deploy_dir / 'conf.py').read_text(), 'custom')
            self.assertIn('Modified files kept:', result.output)
            self.assertIn('deploy/conf.py differs from the template',
                          result.output)
            self.assertTrue((deploy_dir / 'web.py').exists())
