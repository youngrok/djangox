import sys
import warnings
import ipaddress
from pathlib import Path

import boto3
from aws_cdk import App, CfnOutput, CliCredentialsStackSynthesizer, Duration, Environment, Fn, RemovalPolicy, Stack, Tags
from aws_cdk import aws_autoscaling as autoscaling
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticache as elasticache
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_rds as rds
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_route53_targets as route53_targets
from aws_cdk import aws_s3 as s3
from constructs import Construct

warnings.filterwarnings('ignore', message='Typeguard cannot check')

sys.path.append(Path(__file__).parent.as_posix())

from conf import Conf


WEB_ROLE_NAME = 'ec2-role'


def aws_account_id():
    session = boto3.Session(profile_name=Conf.aws_profile, region_name=Conf.aws_region)
    return session.client('sts').get_caller_identity()['Account']


def ec2_client():
    return boto3.Session(profile_name=Conf.aws_profile,
                         region_name=Conf.aws_region).client('ec2')


def selected_vpc_id():
    filters = [{'Name': 'tag:Name', 'Values': [Conf.vpc_name]}] \
        if Conf.vpc_name else [{'Name': 'is-default', 'Values': ['true']}]
    vpcs = ec2_client().describe_vpcs(Filters=filters)['Vpcs']
    if len(vpcs) != 1:
        target = Conf.vpc_name or 'default VPC'
        raise ValueError(f'Expected one VPC for {target}, found {len(vpcs)}')
    return vpcs[0]['VpcId']


def subnets(vpc_id):
    return ec2_client().describe_subnets(
        Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
    )['Subnets']


def route_tables(vpc_id):
    return ec2_client().describe_route_tables(
        Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
    )['RouteTables']


def route_table_by_subnet(vpc_id):
    tables = route_tables(vpc_id)
    by_subnet = {}
    main = None
    for table in tables:
        for association in table.get('Associations', []):
            if association.get('Main'):
                main = table
            if association.get('SubnetId'):
                by_subnet[association['SubnetId']] = table
    return by_subnet, main


def is_public_route_table(table):
    return any(
        route.get('DestinationCidrBlock') == '0.0.0.0/0'
        and route.get('GatewayId', '').startswith('igw-')
        for route in table.get('Routes', [])
    )


def tag_value(resource, key):
    for tag in resource.get('Tags', []):
        if tag.get('Key') == key:
            return tag.get('Value', '')
    return ''


def is_managed_private_subnet(subnet):
    return tag_value(subnet, 'Name').startswith(f'{Conf.project_name}-private-')


def existing_private_subnets(vpc_id):
    by_subnet, main = route_table_by_subnet(vpc_id)
    return [
        subnet
        for subnet in subnets(vpc_id)
        if not is_public_route_table(by_subnet.get(subnet['SubnetId'], main))
        and not is_managed_private_subnet(subnet)
    ]


def managed_private_subnets(vpc_id):
    by_subnet, main = route_table_by_subnet(vpc_id)
    return [
        subnet
        for subnet in sorted(subnets(vpc_id), key=lambda subnet: tag_value(subnet, 'Name'))
        if not is_public_route_table(by_subnet.get(subnet['SubnetId'], main))
        and is_managed_private_subnet(subnet)
    ]


def free_private_cidrs(vpc_id, count):
    if count == 0:
        return []
    vpc = ec2_client().describe_vpcs(VpcIds=[vpc_id])['Vpcs'][0]
    network = ipaddress.ip_network(vpc['CidrBlock'])
    used = [ipaddress.ip_network(subnet['CidrBlock']) for subnet in subnets(vpc_id)]
    cidrs = []
    for cidr in network.subnets(new_prefix=max(network.prefixlen, 24)):
        if all(not cidr.overlaps(existing) for existing in used + cidrs):
            cidrs.append(cidr)
        if len(cidrs) == count:
            return [str(cidr) for cidr in cidrs]
    raise ValueError(f'Not enough free CIDR blocks in {vpc_id}')


def private_subnet_azs(vpc_id, existing, count):
    used = {subnet['AvailabilityZone'] for subnet in existing}
    candidates = [
        subnet['AvailabilityZone']
        for subnet in sorted(subnets(vpc_id),
                             key=lambda subnet: subnet['AvailabilityZone'])
        if subnet['AvailabilityZone'] not in used
    ]
    azs = list(dict.fromkeys(candidates))
    if len(azs) < count:
        raise ValueError(f'Not enough availability zones in {vpc_id}')
    return azs[:count]


def created_private_subnets(scope, vpc_id, existing):
    managed = managed_private_subnets(vpc_id)
    count = max(0, 2 - len(existing), len(managed))
    cidrs = [subnet['CidrBlock'] for subnet in managed[:count]]
    azs = [subnet['AvailabilityZone'] for subnet in managed[:count]]
    missing = count - len(cidrs)
    cidrs += free_private_cidrs(vpc_id, missing)
    azs += private_subnet_azs(vpc_id, existing + managed, missing)
    result = []
    for index in range(count):
        route_table = ec2.CfnRouteTable(scope, f'PrivateRouteTable{index + 1}',
                                        vpc_id=vpc_id)
        subnet = ec2.CfnSubnet(scope, f'PrivateSubnet{index + 1}',
                               vpc_id=vpc_id,
                               cidr_block=cidrs[index],
                               availability_zone=azs[index],
                               map_public_ip_on_launch=False)
        ec2.CfnSubnetRouteTableAssociation(
            scope, f'PrivateSubnetAssociation{index + 1}',
            subnet_id=subnet.ref,
            route_table_id=route_table.ref,
        )
        Tags.of(subnet).add('Name', f'{Conf.project_name}-private-{index + 1}')
        result.append(ec2.Subnet.from_subnet_attributes(
            scope, f'CreatedPrivateSubnet{index + 1}',
            subnet_id=subnet.ref,
            availability_zone=azs[index],
            route_table_id=route_table.ref,
        ))
    return result


def private_subnets(scope, vpc_id):
    existing = existing_private_subnets(vpc_id)
    imported = [
        ec2.Subnet.from_subnet_id(scope, f'ExistingPrivateSubnet{index + 1}',
                                  subnet['SubnetId'])
        for index, subnet in enumerate(existing)
    ]
    return imported + created_private_subnets(scope, vpc_id, existing)


def simple_network(scope):
    vpc_id = selected_vpc_id()
    vpc = ec2.Vpc.from_lookup(scope, 'Vpc', vpc_id=vpc_id)
    data_subnets = private_subnets(scope, vpc_id)
    return (
        vpc,
        ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        ec2.SubnetSelection(subnets=data_subnets),
        data_subnets,
    )


def standard_network(scope):
    vpc = ec2.Vpc(scope, 'Vpc',
                 ip_addresses=ec2.IpAddresses.cidr('10.20.0.0/16'),
                 max_azs=2,
                 nat_gateways=1,
                 subnet_configuration=[
                     ec2.SubnetConfiguration(name='public',
                                             subnet_type=ec2.SubnetType.PUBLIC,
                                             cidr_mask=24),
                     ec2.SubnetConfiguration(name='private',
                                             subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                                             cidr_mask=24),
                 ])
    return (
        vpc,
        ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        vpc.private_subnets,
    )


def network_config(scope):
    if Conf.network == 'simple':
        return simple_network(scope)
    if Conf.network == 'standard':
        return standard_network(scope)
    raise ValueError(f'Unknown network: {Conf.network}')


class WebStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id,
                         synthesizer=CliCredentialsStackSynthesizer(),
                         **kwargs)
        Tags.of(self).add('project', Conf.project_name)

        vpc, web_subnets, data_subnets, data_subnet_list = network_config(self)
        bucket = s3.Bucket(self, 'StorageBucket',
                           bucket_name=Conf.storage_bucket_name,
                           block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                           encryption=s3.BucketEncryption.S3_MANAGED,
                           removal_policy=RemovalPolicy.RETAIN)
        role = iam.Role.from_role_name(self, 'Ec2Role', WEB_ROLE_NAME, mutable=True)
        iam.CfnRolePolicy(self, 'Ec2AppAccess',
                          role_name=WEB_ROLE_NAME,
                          policy_name=f'{Conf.project_name}-app-access',
                          policy_document={
                              'Version': '2012-10-17',
                              'Statement': [
                                  {'Effect': 'Allow',
                                   'Action': ['s3:ListBucket'],
                                   'Resource': bucket.bucket_arn,
                                   'Condition': {'StringLike': {'s3:prefix': ['attachments/*']}}},
                                  {'Effect': 'Allow',
                                   'Action': ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'],
                                   'Resource': bucket.arn_for_objects('attachments/*')},
                                  {'Effect': 'Allow',
                                   'Action': [
                                       'ssm:DescribeAssociation',
                                       'ssm:GetDeployablePatchSnapshotForInstance',
                                       'ssm:GetDocument',
                                       'ssm:DescribeDocument',
                                       'ssm:GetManifest',
                                       'ssm:GetParameter',
                                       'ssm:GetParameters',
                                       'ssm:ListAssociations',
                                       'ssm:ListInstanceAssociations',
                                       'ssm:PutInventory',
                                       'ssm:PutComplianceItems',
                                       'ssm:PutConfigurePackageResult',
                                       'ssm:UpdateAssociationStatus',
                                       'ssm:UpdateInstanceAssociationStatus',
                                       'ssm:UpdateInstanceInformation',
                                       'ssmmessages:CreateControlChannel',
                                       'ssmmessages:CreateDataChannel',
                                       'ssmmessages:OpenControlChannel',
                                       'ssmmessages:OpenDataChannel',
                                       'ec2messages:AcknowledgeMessage',
                                       'ec2messages:DeleteMessage',
                                       'ec2messages:FailMessage',
                                       'ec2messages:GetEndpoint',
                                       'ec2messages:GetMessages',
                                       'ec2messages:SendReply',
                                   ],
                                   'Resource': '*'},
                              ],
                          })

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            'set -eux',
            'apt-get update',
            'DEBIAN_FRONTEND=noninteractive apt-get install -y ec2-instance-connect',
            'snap install amazon-ssm-agent --classic || true',
            'systemctl enable snap.amazon-ssm-agent.amazon-ssm-agent.service || true',
            'systemctl start snap.amazon-ssm-agent.amazon-ssm-agent.service || true',
        )
        asg = autoscaling.AutoScalingGroup(self, 'Web',
                                           vpc=vpc,
                                           role=role,
                                           instance_type=ec2.InstanceType(Conf.instance_type),
                                           machine_image=ec2.MachineImage.lookup(name=Conf.ubuntu_ami_name,
                                                                                 owners=['099720109477']),
                                           min_capacity=1,
                                           max_capacity=1,
                                           health_checks=autoscaling.HealthChecks.ec2(),
                                           user_data=user_data,
                                           associate_public_ip_address=Conf.network == 'simple',
                                           vpc_subnets=web_subnets)
        data_sg = ec2.SecurityGroup(self, 'DataSg', vpc=vpc, allow_all_outbound=True)
        data_sg.connections.allow_from(asg, ec2.Port.tcp(5432))
        data_sg.connections.allow_from(asg, ec2.Port.tcp(6379))

        zone = route53.HostedZone.from_lookup(self, 'HostedZone', domain_name=Conf.server_name)
        certificate = acm.Certificate(self, 'Certificate',
                                      domain_name=Conf.server_name,
                                      validation=acm.CertificateValidation.from_dns(zone))
        alb = elbv2.ApplicationLoadBalancer(self, 'Alb',
                                            vpc=vpc,
                                            internet_facing=True,
                                            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC))
        alb.add_listener('Http', port=80, open=True).add_action(
            'RedirectHttps',
            action=elbv2.ListenerAction.redirect(protocol='HTTPS', port='443', permanent=True),
        )
        alb.add_listener('Https', port=443, open=True, certificates=[certificate]).add_targets(
            'WebTargets',
            port=80,
            targets=[asg],
            health_check=elbv2.HealthCheck(path=Conf.health_path, healthy_http_codes='200-399'),
        )
        route53.ARecord(self, 'Domain',
                        zone=zone,
                        record_name=Conf.server_name,
                        target=route53.RecordTarget.from_alias(route53_targets.LoadBalancerTarget(alb)))

        db = rds.DatabaseInstance(self, 'Db',
                                  vpc=vpc,
                                  database_name=Conf.db_name,
                                  instance_identifier=Conf.db_identifier,
                                  credentials=rds.Credentials.from_generated_secret(Conf.db_username),
                                  engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_16),
                                  instance_type=ec2.InstanceType(Conf.rds_instance_class.removeprefix('db.')),
                                  allocated_storage=20,
                                  backup_retention=Duration.days(7),
                                  deletion_protection=Conf.deletion_protection,
                                  multi_az=False,
                                  publicly_accessible=False,
                                  security_groups=[data_sg],
                                  storage_encrypted=True,
                                  vpc_subnets=data_subnets,
                                  removal_policy=RemovalPolicy.RETAIN if Conf.deletion_protection else RemovalPolicy.DESTROY)
        iam.CfnRolePolicy(self, 'Ec2SecretRead',
                          role_name=WEB_ROLE_NAME,
                          policy_name=f'{Conf.project_name}-secret-read',
                          policy_document={
                              'Version': '2012-10-17',
                              'Statement': [
                                  {'Effect': 'Allow',
                                   'Action': ['secretsmanager:GetSecretValue'],
                                   'Resource': [
                                       f'arn:aws:secretsmanager:{Conf.aws_region}:{self.account}:secret:{Conf.common_secret_name}-*',
                                       f'arn:aws:secretsmanager:{Conf.aws_region}:{self.account}:secret:{Conf.secret_name}-*',
                                       db.secret.secret_arn,
                                   ]},
                                  {'Effect': 'Allow',
                                   'Action': ['rds:DescribeDBInstances'],
                                   'Resource': '*'},
                              ],
                          })
        redis_subnets = elasticache.CfnSubnetGroup(self, 'RedisSubnets',
                                                  description=f'{Conf.project_name} redis subnets',
                                                  subnet_ids=[subnet.subnet_id for subnet in data_subnet_list])
        redis = elasticache.CfnCacheCluster(self, 'Redis',
                                            engine='redis',
                                            engine_version='7.1',
                                            cache_node_type=Conf.redis_node_type,
                                            num_cache_nodes=1,
                                            cache_parameter_group_name='default.redis7',
                                            port=6379,
                                            cache_subnet_group_name=redis_subnets.ref,
                                            vpc_security_group_ids=[data_sg.security_group_id])

        CfnOutput(self, 'VpcId', value=vpc.vpc_id)
        CfnOutput(self, 'PublicSubnetIds', value=Fn.join(',', [subnet.subnet_id for subnet in vpc.public_subnets]))
        CfnOutput(self, 'PrivateSubnetIds', value=Fn.join(',', [subnet.subnet_id for subnet in data_subnet_list]))
        CfnOutput(self, 'AlbDnsName', value=alb.load_balancer_dns_name)
        CfnOutput(self, 'DomainName', value=Conf.server_name)
        CfnOutput(self, 'AsgName', value=asg.auto_scaling_group_name)
        CfnOutput(self, 'BucketName', value=bucket.bucket_name)
        CfnOutput(self, 'SecretName', value=Conf.secret_name)
        CfnOutput(self, 'DbEndpoint', value=db.db_instance_endpoint_address)
        CfnOutput(self, 'DbSecretArn', value=db.secret.secret_arn)
        CfnOutput(self, 'RedisEndpoint', value=redis.attr_redis_endpoint_address)


app = App(analytics_reporting=False)
WebStack(app, f'{Conf.project_name}-{Conf.environment}',
         env=Environment(account=aws_account_id(), region=Conf.aws_region))
app.synth()
