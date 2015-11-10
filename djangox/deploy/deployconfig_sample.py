from fabric.state import env

env.roledefs.update({
    'web': [
        'webserver1.com',
        'webserver2.com'
    ],
    'db': ['dbserver1.com']
})

env.server_name = 'mydomain.com'
env.project_name = 'myproject'
env.project_repo = 'git@github.com:me/myproject.git'

env.key_filename = 'mykey.pem'
env.backup_bucket = 'myproject-backup'

env.db_host = 'dbserver1.com'
env.db_name = 'mydbname'
env.db_user = 'mydbuser'
env.db_password = 'mydbpassword'
