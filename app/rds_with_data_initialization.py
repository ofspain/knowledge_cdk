import uuid

import aws_cdk as cdk
import os
from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_logs as logs,
    Duration,
    custom_resources as cr,
    aws_secretsmanager as secretsmanager,
    CfnOutput,
)
from constructs import Construct

from app.rds_stack import (RdsStack,InstanceType)
from app.vpc_stack import VpcStack

class RdsWithInitializationStack(RdsStack):
    def __init__(
        self,
        scope: Construct,
        instance_type: InstanceType,
        construct_id: str,
        vpc_stack: VpcStack,
        database_name:str,
        **kwargs,
    ) -> None:
        super().__init__(scope, instance_type, construct_id, vpc_stack, database_name, **kwargs)

        # add role for lambda execution with least privilege
        #########
        ### Provides minimum permissions for a Lambda function to execute
        ### while accessing a resource within a VPC
        #########
        lambda_role = iam.Role(
            self, "DbInitLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole"),
            ]
        )

        # Lambda (Docker Image)
        docker_lambda = _lambda.DockerImageFunction(
            self, "DbInitFunction",
            function_name="app-db-initializer",
            code=_lambda.DockerImageCode.from_image_asset(
                directory=os.path.join(os.path.dirname(__file__), "lambda"),
                file="Dockerfile"
            ),
            timeout=Duration.minutes(5),
            memory_size=1024,
            vpc=vpc_stack.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[self.rds_sg],
            environment={
                "DB_SECRET_ARN": self.db_credentials_secret.secret_arn,
                "DB_ENDPOINT": self.db_instance.db_instance_endpoint_address,
                "DB_NAME": database_name,
                "LOG_LEVEL": "INFO"
            },
            role=lambda_role,
            log_retention=logs.RetentionDays.ONE_MONTH
        )

        # Grant permissions to lambda
        self.db_instance.secret.grant_read(docker_lambda)
        self.rds_sg.add_ingress_rule(
            self.rds_sg,
            ec2.Port.tcp(self.db_instance.port),
            "Allow lambda to access database"
        )

        # Custom Resource with retry and timeout handling
        provider = cr.Provider(
            self, "DbInitProvider",
            on_event_handler=docker_lambda,
            log_retention=logs.RetentionDays.ONE_MONTH,
            total_timeout=Duration.minutes(30),
            query_interval=Duration.seconds(30)
        )

        # Custom Resource with dependency on DB being available
        init_resource = cr.CustomResource(
            self, "DbInitializer",
            service_token=provider.service_token,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )
        init_resource.node.add_dependency(self.db_instance)

        # Outputs
        # CfnOutput(
        #     self, "DbEndpoint",
        #     value=db.db_instance_endpoint_address,
        #     description="Database connection endpoint"
        # )
        # CfnOutput(
        #     self, "DbSecretArn",
        #     value=db.secret.secret_arn,
        #     description="ARN of the database secret"
        # )

