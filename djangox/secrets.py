import json
import os
from pathlib import Path
from urllib.parse import quote


def get_secrets(secret_name, region_name='ap-northeast-2', profile_name=None):
    import boto3

    session = boto3.session.Session(
        profile_name=profile_name or os.environ.get('AWS_PROFILE'))
    client = session.client(service_name='secretsmanager', region_name=region_name)
    return json.loads(client.get_secret_value(SecretId=secret_name)['SecretString'])


def create_secret(secret_name, values=None, region_name='ap-northeast-2',
                  profile_name=None):
    import boto3

    session = boto3.session.Session(
        profile_name=profile_name or os.environ.get('AWS_PROFILE'))
    client = session.client(service_name='secretsmanager', region_name=region_name)
    secret_string = json.dumps(values or {}, ensure_ascii=False)
    try:
        client.create_secret(Name=secret_name, SecretString=secret_string)
        return True
    except client.exceptions.ResourceExistsException:
        return False


def secrets_console_url(project_name, region_name='ap-northeast-2'):
    return 'https://{0}.console.aws.amazon.com/secretsmanager/listsecrets?region={0}&search={1}'.format(
        region_name,
        quote(f'keys-{project_name}', safe=''))


def secret_console_url(secret_name, region_name='ap-northeast-2'):
    return 'https://{0}.console.aws.amazon.com/secretsmanager/home?region={0}#!/secret?name={1}'.format(
        region_name,
        quote(secret_name, safe=''))


def write_secret_settings(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dict_to_python_code(values), encoding='utf-8')
    os.chmod(path, 0o600)


def dict_to_python_code(values):
    return ''.join([f'{key} = {value!r}\n' for key, value in values.items()])
