from datetime import date
from fabric.context_managers import cd, settings
from fabric.operations import run, sudo
from fabric.contrib.files import exists
from fabric.decorators import task, roles
from fabric.state import env
from fabtools import require
import fabtools
from fabtools.python import virtualenv
import deployconfig


env.user = 'ubuntu'
env.home = '/home/' + env.user
env.project_path = env.home + '/' + env.project_name
env.static_path = env.home + '/static'
env.deploy_key_path = env.home + '/.ssh/' + 'id_deploy'
env.virtualenv = env.home + '/venv'
env.backup_dir = '/mnt/data'


def checkout(url, directory):
    if exists(directory):
        with cd(directory):
            run("ssh-agent bash -c 'ssh-add %s; git pull'" % env.deploy_key_path)

    else:
        with cd(env.home):
            run("ssh-agent bash -c 'ssh-add %s; git clone %s'" % (env.deploy_key_path, url))


@task
@roles('web')
def setup_web():
    require.deb.packages(['git', 'npm', 'nodejs-legacy', 'python3-dev', 'libxml2-dev', 'libxslt1-dev', 'libpq-dev'])
    require.nginx.server()
    require.nginx.site(env.server_name, template_source='nginx-site',
                       port=80,
                       server_alias='',
                       static_path=env.static_path)
    # require.nginx.disabled('default')

    with settings(warn_only=True):
        if run('type bower').return_code:
            sudo('npm install -g bower')

    update_source()

    require.directory(env.home + '/logs')
    require.python.packages(['uwsgi', 'virtualenv', 'ipython', 'celery'], use_sudo=True)
    require.file('/etc/init/uwsgi.conf', source='uwsgi.conf', use_sudo=True)
    # require.file('/etc/init/celery.conf', source='celery.conf', use_sudo=True)
    require.directory('/etc/uwsgi', use_sudo=True)
    require.files.template_file('/etc/uwsgi/%s.ini' % env.project_name,
                                template_source='uwsgi.ini',
                                context=env, use_sudo=True)
    require.service.started('uwsgi')
    require.directory(env.home + '/bin')
    require.files.template_file(env.home + '/bin/djangorc',
                                template_source='bin/djangorc',
                                context=env)
    require.files.template_file(env.home + '/bin/loadenv',
                                template_source='bin/loadenv',
                                context=env)
    run('chmod +x ' + env.home + '/bin/loadenv')

    # require.service.started('celery')


@task
@roles('db')
def setup_db():
    require.deb.packages(['postgresql', 'libpq-dev'])
    if not fabtools.postgres.user_exists(env.db_user):
        fabtools.postgres.create_user(env.db_user, env.db_password, createdb=True)

    if not fabtools.postgres.database_exists(env.project_name):
        fabtools.postgres.create_database(env.project_name, env.project_name)

    # require.python.package('awscli', use_sudo=True)
    # require.files.directory(env.home + '/.aws')
    # require.files.template_file(env.home + '/.aws',
    #                             template_source='.aws/config', context=env)
    # require.files.template_file(env.home + '/.aws',
    #                             template_source='.aws/credentials', context=env)
    # run('chmod 0600 ' + env.home + '/.aws/*')

    require.directory(env.backup_dir, use_sudo=True)
    sudo('chown ubuntu.ubuntu %s' % env.backup_dir)
    # require.files.template_file(env.home + '/bin/backup-postgresql.sh',
    #                             template_source='bin/backup-postgresql.sh',
    #                             context=env)
    # run('chmod +x ' + env.home + '/bin/backup-postgresql.sh')
    # fabtools.cron.add_task('backup-postgresql',
    #                        '0 0 * * *',
    #                        'ubuntu',
    #                        '%s/bin/backup-postgresql.sh' % env.home)


@task
@roles('web')
def deploy():
    update_source()
    require.service.restart('uwsgi')
    # require.service.restart('celery')


@roles('web')
def update_source():
    require.file(env.deploy_key_path, source='id_deploy')
    run('chmod 0600 ' + env.deploy_key_path)
    checkout(env.project_repo, env.project_path)
    require.files.template_file(env.project_path + '/%s/production.py' % env.project_name,
                                template_source='production.py.template', context=env)

    require.python.virtualenv(env.virtualenv, venv_python='/usr/bin/python3')
    with virtualenv(env.virtualenv):
        require.python.requirements(env.project_path + '/requirements.txt')
        with cd(env.project_path):
            run('bower install')
            run('./manage.py collectstatic --settings=%s.production --noinput' % env.project_name)
            run('./manage.py migrate --settings=%s.production --noinput' % env.project_name)
