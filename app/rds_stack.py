import uuid

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager,
    CfnOutput,
)
from constructs import Construct

from app.vpc_stack import VpcStack


import enum

class InstanceType(enum.Enum):
    POSTGRES = "Postgres"
    MYSQL = "MySQL"
    ORACLE = "Oracle"


def provision_db_engine(instance_type: InstanceType) -> rds.DatabaseInstanceEngine:
    db_engine = rds.DatabaseInstanceEngine()

    if instance_type == InstanceType.MYSQL:
        db_engine = rds.DatabaseInstanceEngine.mysql(
            version=rds.MysqlEngineVersion.VER_8_0_39
        )
    elif instance_type == InstanceType.POSTGRES:
        db_engine = rds.DatabaseInstanceEngine.postgres(
            version=rds.PostgresEngineVersion.VER_16_3
        )
    elif instance_type == InstanceType.ORACLE:
        db_engine = rds.DatabaseInstanceEngine.oracle(
            version=rds.OracleEngineVersion.VER_19_0_0_0_2020_04_R1
        )

    return db_engine


class RdsStack(Stack):
    def __init__(
        self,
        scope: Construct,
        instance_type: InstanceType,
        construct_id: str,
        vpc_stack: VpcStack,
        database_name:str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = vpc_stack.vpc
        self.rds_sg = None
        self.port = 3306
        self.provision_security_group(vpc_stack.ec2_sg, instance_type)

        # Create a secret for RDS credentials
        self.db_credentials_secret = self.provision_db_credentials_secret(instance_type)

        # Create a subnet group for RDS
        rds_subnet_group = self.provision_subnet_group()

        # Provision the RDS instance
        self.db_instance = rds.DatabaseInstance(
            self,
            "RdsInstance",
            # instance_type=ec2.InstanceType.of(
            #     ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MEDIUM
            # ),  # Use t3.medium for production
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3,
                ec2.InstanceSize.SMALL
            ),# Use t3.medium for testing
            engine= provision_db_engine(instance_type),
            credentials=rds.Credentials.from_secret(self.db_credentials_secret),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            database_name=database_name,
            publicly_accessible=False,
            security_groups=[self.rds_sg],
            multi_az=True,  # Enable Multi-AZ for high availability
            storage_type=rds.StorageType.GP2,  # Use General Purpose SSD
            allocated_storage=100,  # Allocate 100 GB of storage
            max_allocated_storage=200,  # Enable storage autoscaling up to 200 GB
            backup_retention=cdk.Duration.days(7),  # Retain backups for 7 days
            deletion_protection=True,  # Protect against accidental deletion
            removal_policy=cdk.RemovalPolicy.SNAPSHOT,  # Take a snapshot on deletion
            subnet_group=rds_subnet_group,  # Use the subnet group
        )

        # Output the RDS instance endpoint and secret ARN
        # We can use this endpoint to connect to the db esp if the security group allow ingress
        CfnOutput(
            self,
            "DBInstanceEndpoint",
            value=self.db_instance.db_instance_endpoint_address,
        )
        CfnOutput(
            self,
            "DBInstanceSecretArn",
            value=self.db_credentials_secret.secret_arn,
        )

        CfnOutput(
            self,
            "DBInstanceSecretName",
            value=self.db_credentials_secret.secret_name,
        )

    def provision_security_group(self, ec2_sg: ec2.SecurityGroup, instance_type: InstanceType) -> None:
        # Create Security Group for RDS (Database)
        instance_sg = ec2.SecurityGroup(
            self,
            "RDSSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=True,  # Allows RDS to initiate outbound connections if needed
        )

        #Allow Application EC2 Access db


        if instance_type==InstanceType.POSTGRES:
            self.port = 5432
        elif instance_type==InstanceType.ORACLE:
            self.port = 1521
        instance_sg.add_ingress_rule(
            peer=ec2_sg,
            connection=ec2.Port.tcp(self.port),
            description="Allow Connection from EC2 to RDS",
        )

        self.rds_sg = instance_sg

    def provision_subnet_group(self) -> rds.SubnetGroup:
        rds_subnet_group = rds.SubnetGroup(
            self,
            "MyRdsSubnetGroup",
            vpc=self.vpc,
            description="Subnet group for RDS",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS  # Select private subnets
            ),
        )
        return rds_subnet_group

    def provision_db_credentials_secret(self, instance_type) -> secretsmanager.Secret:
        identifier = ""
        username = ""
        suffix = f"rds-credentials-{uuid.uuid4()}"
        if instance_type == InstanceType.POSTGRES:
            identifier = f"postgres-{suffix}"
            username = "postgres"
        elif instance_type == InstanceType.MYSQL:
            identifier = f"mysql-{suffix}"
            username = "admin"
        elif instance_type == InstanceType.ORACLE:
            identifier = f"oracle-{suffix}"
            username = "admin"

        cred = secretsmanager.Secret(
            self,
            "RdsCredentialsSecret",
            secret_name=f"{identifier}-rds-credentials",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=f'{{"username": "{username}"}}',  # Properly format the string
                generate_string_key="password",
                exclude_characters='"@/\\'
            )
        )

        return cred
