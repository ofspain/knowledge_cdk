import json
import os
from typing import Mapping, Any, Dict

from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_s3 as s3,
    aws_iam as iam,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_servicediscovery as sd,
    aws_ssm as ssm,
    aws_secretsmanager as secretsmanager, SecretValue
)
from constructs import Construct

from app.vpc_stack import VpcStack
from .InfraStack import InfraStack
from .utility.secret_extractor import AwsSecretsManagerService as secrets_manager

class ECSAppStack(Stack):
    def __init__(self, scope: Construct, stack_id: str, cluster_name: str,
                 image_uri, app_name: str, environment_name: str, **kwargs):
        super().__init__(scope, stack_id, **kwargs)

        self.environment_name  = environment_name
        self.app_name = app_name
        self.image_uri = image_uri
        vpc_id = ssm.StringParameter.value_from_lookup(self, "vpcstack_vpc_vpc_id")

        self.vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_id=vpc_id)

        self.cluster = self.import_ecs_cluster(cluster_name, self.vpc)

        self.config = self.load_config_static_folder()
        environment = self.prepare_environment(self.config.get("plain_parameters"))

        account_parameters = {
            "REGION":self.node.try_get_context("region"),
        }

        print(f"DEBUG: REGION set to {account_parameters.get('REGION')}")

        self.secrets_manager = secrets_manager(self.config.get("secrete_parameters"), account_parameters)

        secrets = self.prepare_secrets()

        name_space_name = self.cluster.cluster_name + "." + "ofspain"
        self.namespace = sd.PrivateDnsNamespace(
            self, "ServiceDiscoveryNamespace",
            name=name_space_name,
            vpc=self.vpc
        )



        self.execution_role = iam.Role(
            self, "AppExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )

        # IAM Roles
        task_role = iam.Role(
            self, "AppTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )
        self.task_definition = ecs.Ec2TaskDefinition(self,self.app_name+"Task",
                                                     task_role=task_role,execution_role = self.execution_role)

        container_image = ecs.ContainerImage.from_registry(self.image_uri)

        self.task_definition.add_container(
            self.app_name+"Container",
            image=container_image,
            memory_limit_mib=512,
            environment=environment,
            secrets=secrets,
            port_mappings=[ecs.PortMapping(container_port=8080, host_port=80)]
        )

        self.ecs_service = ecs.Ec2Service(
            self, self.app_name+"Service",
            cluster=self.cluster,
            task_definition=self.task_definition,
            cloud_map_options=ecs.CloudMapOptions(
                name=self.app_name,
                cloud_map_namespace=self.namespace
            ),
            desired_count=2
        )

    # def load_config_from_s3(self)->Dict[str, Mapping[Any, Any]]:
    #     #todo: rewrite using boto3 to access s3...externalize this to a utility lambda function
    #     """Load the configuration file from S3."""
    #     key = "configs/" + self.environment_name + ".env.json"
    #     bucket = ....
    #     response = s3.get_object(Bucket=bucket, Key=key)
    #     content = response['Body'].read().decode('utf-8')
    #     return json.loads(content)

    def load_config_static_folder(self) -> Dict[str, Mapping[Any, Any]]:
        """
        Load configuration from a static JSON file in the `config` folder.
        Assumes the file is named `my_file.env.json` and lives in `config/` relative to this module.
        """
        # Construct the path to the config file
        config_filename = f"{self.environment_name}.env.json"
        config_path = os.path.join(os.path.dirname(__file__), "config", config_filename)

        # Read and parse the file
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found at {config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")

        # Validate top-level keys (optional but recommended)
        if "plain_parameters" not in config or "secrete_parameters" not in config:
            raise ValueError("Configuration file must contain 'environment' and 'secrets' keys")

        return config



    def prepare_secrets(self):
        """Prepare sensitive environment variables"""
        # https://medium.com/@davidnsoesie1/stop-exposing-secrets-in-your-infrastructure-as-code-0b907694a8c1
        db_secret_map = self.secrets_manager.get_db_secret()

        # secret = secretsmanager.Secret(
        #     self, "MySecret",
        #     secret_name="MyAppSecret",
        #     secret_string_value=SecretValue.unsafe_plain_text("my-plaintext-secret")
        # )
        #
        # # Use it in ECS
        # ecs_secret = ecs.Secret.from_secrets_manager(secret)

        ecs_secret_map = {}

        for key, value in db_secret_map.items():
            # 1. Create individual Secrets Manager secret
            secret = secretsmanager.Secret(
                self, f"MySecret{key.capitalize()}",
                secret_name=f"MyAppSecret-{key}",
                secret_string_value=SecretValue.unsafe_plain_text(value)
            )

            # 2. Create ECS-compatible secret
            ecs_secret = ecs.Secret.from_secrets_manager(secret)

            # 3. Add to result dict with "db_" prefix
            ecs_secret_map[f"db_{key}"] = ecs_secret

        return ecs_secret_map

    def prepare_environment(self, config: Mapping[Any, Any]) -> Dict[str, str]:
        """Prepare non-sensitive environment variables from a config-like object"""
        return {
            str(key): ssm.StringParameter.value_from_lookup(self, str(value))
            for key, value in config.items()
        }

    def import_ecs_cluster(self, cluster_name: str, vpc: ec2.Vpc) -> ecs.ICluster:
        """
        Utility to safely import an existing ECS cluster with its required attributes.
        *NOTE*: cluster_arn = "arn:aws:ecs:us-east-1:012345678910:cluster/clusterName"
                cluster = ecs.Cluster.from_cluster_arn(self, "Cluster", cluster_arn)
        The above too works but properties of the cluster may not be available at runtime.
        """

        cluster = ecs.Cluster.from_cluster_attributes(
            self, "ImportedCluster",
            cluster_name=cluster_name,
            vpc=vpc
        )
        return cluster