import json

import boto3


def session(profile_name=None, region_name='ap-northeast-2'):
    if profile_name:
        return boto3.session.Session(profile_name=profile_name,
                                     region_name=region_name)
    return boto3.session.Session(region_name=region_name)


def client(service_name, profile_name=None, region_name='ap-northeast-2'):
    return session(profile_name, region_name).client(service_name)


def tag_value(resource, name):
    for tag in resource.get('Tags', []):
        if tag.get('Key') == name:
            return tag.get('Value', '')
    return ''


def running_instances(project_name, profile_name=None, region_name='ap-northeast-2',
                      tag_name='project'):
    response = client('ec2', profile_name, region_name).describe_instances(
        Filters=[
            {'Name': f'tag:{tag_name}', 'Values': [project_name]},
            {'Name': 'instance-state-name', 'Values': ['running']},
        ]
    )
    return [
        instance
        for reservation in response['Reservations']
        for instance in reservation['Instances']
    ]


def secret_values(secret_name, profile_name=None, region_name='ap-northeast-2'):
    response = client('secretsmanager', profile_name,
                      region_name).get_secret_value(SecretId=secret_name)
    return json.loads(response.get('SecretString') or '{}')


def ensure_secret(secret_name, profile_name=None, region_name='ap-northeast-2'):
    secretsmanager = client('secretsmanager', profile_name, region_name)
    try:
        secretsmanager.describe_secret(SecretId=secret_name)
        return False
    except secretsmanager.exceptions.ResourceNotFoundException:
        secretsmanager.create_secret(Name=secret_name, SecretString='{}')
        return True


def update_secret_values(secret_name, values, profile_name=None,
                         region_name='ap-northeast-2'):
    ensure_secret(secret_name, profile_name, region_name)
    current = secret_values(secret_name, profile_name, region_name)
    current.update(values)
    client('secretsmanager', profile_name, region_name).put_secret_value(
        SecretId=secret_name,
        SecretString=json.dumps(current, ensure_ascii=False),
    )
    return current


def rds_instance(db_identifier, profile_name=None, region_name='ap-northeast-2'):
    response = client('rds', profile_name, region_name).describe_db_instances(
        DBInstanceIdentifier=db_identifier
    )
    return response['DBInstances'][0]
