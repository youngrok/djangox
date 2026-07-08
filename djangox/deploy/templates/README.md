# Deploy

Use `control.py` from the project root. CDK manages AWS infrastructure in
`deploy/infra.py`; deploy and shell access go through AWS Systems Manager.

```bash
./control.py infra
./control.py infra add production
./control.py infra setup production
./control.py deploy production
./control.py connect
```

Review infrastructure changes and target hosts before setup or deploy.

## Secrets

- Common keys: `{{ project_name }}-keys-dev`
- Production overrides: `{{ project_name }}-keys-production`
- DB credentials: RDS managed secret

Effective app keys:

```text
SECRET_KEY
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET
GITHUB_DEPLOY_KEY
```

`infra add` creates secret shells and the GitHub deploy key when needed.
Deployment sends a command through SSM. The EC2 instance reads common keys,
production overrides, and the RDS managed secret with its IAM role. It does not
mutate secrets during deploy.

## Runtime

Target EC2 instances are tagged `project={{ project_name }}`. The deploy caller
needs SSM SendCommand/StartSession permissions for the target instances.

```text
~/{{ project_name }}-YYMMDD-HHmmss
~/{{ project_name }} -> active release
~/static-YYMMDD-HHmmss
~/static -> active static files
```

The server keeps 2 releases and reloads gunicorn/nginx after switching symlinks.
