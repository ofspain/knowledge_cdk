#!/usr/bin/env python3
import os

import aws_cdk as cdk
from aws_cdk import aws_ssm as ssm

from app.InfraStack import InfraStack
from app.ec2_stack import EC2Stack
from app.lambda_autodeploy_s3_stack import LambdaAutoDeployStack
from app.vpc_stack import VpcStack
from app.rds_mysql_stack import RdsMysqlStack
from app.rds_stack import (RdsStack, InstanceType)
from app.customised_vpc_stack import CustomisedVpcStack
from app.app_stack import ECSAppStack
from app.managed_nginx import EC2WithNginxLBStack



app = cdk.App()
# AppStack(app, "AppStack",
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    #env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    #env=cdk.Environment(account='123456789012', region='us-east-1'),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    # )
# CustomisedVpcStack(app, "CustomisedVpcStack",
#                     env=cdk.Environment(account='774173912604',
#                                         region='us-east-1'),
#                    )

#####################################################################################################
# vpc_stack = VpcStack(app, "VpcStack")
# postgresDBInstance = RdsStack(app, instance_type=InstanceType.POSTGRES,  construct_id="RdsPostgresStack",  vpc_stack=vpc_stack, database_name='key_generator_db')


# rds_endpoint = postgresDBInstance.db_instance.db_instance_endpoint_address
# secret_cred_arn = postgresDBInstance.db_credentials_secret.secret_arn
# secret_cred_name = postgresDBInstance.db_credentials_secret.secret_name

# meta_data = {"rds_endpoint": rds_endpoint, "secret_cred_arn": secret_cred_arn,
#              "secret_cred_name": secret_cred_name, "default_region": "us-east-1"}

# ec2_stack = EC2Stack(app, "EC2Stack", vpc_stack=vpc_stack, meta_data=meta_data)

#dbInstance = RdsMysqlStack(app, "RdsMysqlStack", ec2_sg=ec2_stack.security_group, vpc_stack=vpc_stack)

# lambda_auto_deploy = LambdaAutoDeployStack(app, "LambdaAutoDeploy")
###########################################################################################################

account_details={
     'account': os.environ['CDK_DEFAULT_ACCOUNT'],
     'region': os.environ['CDK_DEFAULT_REGION']
}


vpc_stack = VpcStack(app, "VpcStack", env=account_details)
postgresDBInstance = RdsStack(app, instance_type=InstanceType.POSTGRES,  construct_id="RdsPostgresStack",  vpc_stack=vpc_stack, database_name='key_generator_db', env=account_details)
infra_stack = InfraStack(app, "InfraStack",vpc_stack=vpc_stack, app_ports = [8080], environment_name="dev", env=account_details)

cluster_name = infra_stack.cluster.cluster_name
vpc = vpc_stack.vpc
public_subnet_id = vpc.public_subnets[0].subnet_id
public_subnet_az = vpc.public_subnets[0].availability_zone
security_group_id = vpc_stack.ec2_sg.security_group_id


# app_stack = ECSAppStack(app, "AppStack", cluster_name=cluster_name, image_uri="", app_name="app-name", environment_name="dev", env=account_details)
#
# dns_name = app_stack.namespace
# subnet_params = {'id':public_subnet_id, 'az':public_subnet_az}
#
# nginx_lb = EC2WithNginxLBStack(app, "NginxLb", subnet_params=subnet_params, sg_id=security_group_id, dns=dns_name, env=account_details)

app.synth()

#This is the expected behavior >= 0.36.0. We wanted to reduce the implicit effect the user's
# environment has on the synthesis result as this can cause production risks, so we made this
# explicit. If you don't specify env when a stack is defined, the stack will be "env-agnostic"
# which means that Vpc.fromLookup won't be able to work. If, for development purposes you wish
# your stack to inherit it's environment information from the CLI, you can use the
# CDK_DEFAULT_ACCOUNT and CDK_DEFAULT_REGION environment variables:

# DeploymentStack(
#   app=app,
#   id='Dev',
#   env={
#     'account': os.environ['CDK_DEFAULT_ACCOUNT'],
#     'region': os.environ['CDK_DEFAULT_REGION']
#   }
# )
