# Deploy

This folder deploys the Django web process with pyinfra.

Deployment uses timestamped releases with stable symlinks:

```text
~/{{ project_name }}-YYMMDD-HHmmss
~/{{ project_name }} -> active release
~/static-YYMMDD-HHmmss
~/static -> active static files
```

The deploy script prepares a new release directory, switches the symlinks,
reloads one gunicorn service, reloads nginx, and removes old releases beyond
the configured retention count.

Required AWS Secrets Manager secret:

```text
keys-{{ project_name }}-production
```

Required keys in that secret:

```text
SECRET_KEY
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET
DATABASE_NAME
DATABASE_USER
DATABASE_PASSWORD
DATABASE_HOST
DATABASE_PORT
GITHUB_DEPLOY_KEY
```

The target EC2 instance must be running and tagged:

```text
project={{ project_name }}
```

`GITHUB_DEPLOY_KEY` must be a private key whose public key is registered as a
read-only GitHub deploy key for the project repository.

Run from the project root:

```bash
direnv allow
pyinfra {{ deploy_dir }}/inventory.py {{ deploy_dir }}/web.py
```

Connect to the production server:

```bash
python {{ deploy_dir }}/production.py
python {{ deploy_dir }}/production.py list
python {{ deploy_dir }}/production.py 0
```

`djangox setup` writes `AWS_PROFILE` to `.envrc`. Region defaults to
`{{ aws_region }}` and can be overridden with the standard AWS environment
variables `AWS_REGION` or `AWS_DEFAULT_REGION`.
