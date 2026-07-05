import re
import subprocess
from importlib import resources
from pathlib import Path


TEMPLATE_FILES = {
    'README.md': 'README.md',
    '__init__.py': '__init__.py',
    'conf.py': 'conf.py',
    'production.py': 'production.py',
    'ssh_config': 'ssh_config',
    'web.py': 'web.py',
    'production.py.j2': 'production.py.j2',
    'nginx-site.conf': 'nginx-site.conf',
    'gunicorn.service': 'gunicorn.service',
    'bin/loadenv': 'bin/loadenv',
    'bin/djangorc': 'bin/djangorc',
    'bin/deploy-release': 'bin/deploy-release',
}


def setup_project(server_name, aws_profile, ssh_key, project_name='',
                  repo='', static_dir='', settings_package='',
                  deploy_dir='deploy',
                  djangox_repo='git@github.com:youngrok/djangox.git',
                  aws_region='ap-northeast-2',
                  storage_bucket_name='', force=False):
    repo = repo or detect_repo()
    project_name = project_name or detect_project_name(repo)
    settings_package = settings_package or detect_settings_package(project_name)
    static_dir = static_dir or detect_static_dir()
    result = setup_deploy(project_name, repo, server_name, static_dir,
                          ssh_key, settings_package, deploy_dir,
                          djangox_repo, aws_region, storage_bucket_name,
                          force)
    add_status(result, update_envrc({'AWS_PROFILE': aws_profile}), Path('.envrc'))
    return result


def setup_deploy(project_name, repo, server_name, static_dir, ssh_key='~/.ssh/id_rsa',
                 settings_package='', deploy_dir='deploy',
                 djangox_repo='git@github.com:youngrok/djangox.git',
                 aws_region='ap-northeast-2', storage_bucket_name='',
                 force=False):
    deploy_path = Path(deploy_dir)
    settings_package = settings_package or project_name.replace('-', '_')
    storage_bucket_name = storage_bucket_name or f'{project_name}-files'
    values = {
        'project_name': project_name,
        'settings_package': settings_package,
        'env_prefix': project_name.replace('-', '_').upper(),
        'repo': repo,
        'server_name': server_name,
        'static_dir': static_dir,
        'ssh_key': ssh_key,
        'djangox_repo': djangox_repo,
        'aws_region': aws_region,
        'storage_bucket_name': storage_bucket_name,
        'deploy_dir': deploy_path.as_posix(),
        'project_name_py': repr(project_name),
        'settings_package_py': repr(settings_package),
        'repo_py': repr(repo),
        'server_name_py': repr(server_name),
        'static_dir_py': repr(static_dir),
        'ssh_key_py': repr(ssh_key),
        'djangox_repo_py': repr(djangox_repo),
        'aws_region_py': repr(aws_region),
        'storage_bucket_name_py': repr(storage_bucket_name),
    }
    result = new_result()
    for template, target in TEMPLATE_FILES.items():
        path = deploy_path / target
        content = render_template(template, values)
        add_status(result, write_if_needed(path, content, force), path)

    add_status(result, update_gitignore(deploy_path.as_posix()), Path('.gitignore'))
    return result


def render_template(name, values):
    template = resources.files('djangox.deploy').joinpath('templates', name).read_text(encoding='utf-8')
    return re.sub(r'\{\{\s*([a-z_]+)\s*\}\}', lambda match: str(values.get(match.group(1), match.group(0))), template)


def new_result():
    return {
        'created': [],
        'updated': [],
        'unchanged': [],
        'modified': [],
    }


def add_status(result, status, path):
    result[status].append(path)


def write_if_needed(path, content, force=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding='utf-8')
        return 'created'
    if path.read_text(encoding='utf-8') == content:
        return 'unchanged'
    if force:
        path.write_text(content, encoding='utf-8')
        return 'updated'
    return 'modified'


def update_gitignore(deploy_dir):
    path = Path('.gitignore')
    existed = path.exists()
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    original = list(lines)
    for line in [f'{deploy_dir}/*.pem']:
        if line not in lines:
            lines.append(line)
    if lines == original:
        return 'unchanged'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return 'updated' if existed else 'created'


def detect_project_name(repo):
    name = repo.rstrip('/').rsplit('/', 1)[-1]
    if name.endswith('.git'):
        name = name[:-4]
    return name or Path.cwd().name


def detect_repo():
    repo = run(['git', 'config', '--get', 'remote.origin.url'])
    if not repo:
        raise ValueError('Cannot detect git remote origin. Pass --repo.')
    return repo


def detect_settings_package(project_name):
    manage_py = Path('manage.py')
    if manage_py.exists():
        match = re.search(
            r"DJANGO_SETTINGS_MODULE',\s*'([^']+)\.settings'",
            manage_py.read_text(encoding='utf-8'),
        )
        if match:
            return match.group(1)

    candidates = [
        path.parent.as_posix()
        for path in Path('.').glob('*/settings.py')
        if not path.as_posix().startswith(('.', 'deploy/'))
    ]
    if len(candidates) == 1:
        return candidates[0]
    return project_name.replace('-', '_')


def detect_static_dir():
    candidates = [
        path.parent.as_posix()
        for path in Path('.').glob('*/static/package.json')
        if 'node_modules' not in path.parts
    ]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError('Cannot detect static dir. Pass --static-dir.')
    raise ValueError('Multiple static dirs found. Pass --static-dir.')


def run(command):
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        return ''
    return result.stdout.strip()


def update_envrc(values):
    path = Path('.envrc')
    existed = path.exists()
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    original = list(lines)
    for key, value in values.items():
        line = f'export {key}={value}'
        replaced = False
        for index, existing in enumerate(lines):
            if existing.startswith(f'export {key}=') or existing.startswith(f'{key}='):
                lines[index] = line
                replaced = True
                break
        if not replaced:
            lines.append(line)
    if lines == original:
        return 'unchanged'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return 'updated' if existed else 'created'
