import json
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_servicediscovery as sd,
    aws_autoscaling as autoscaling,
    aws_ssm as ssm,
    aws_secretsmanager as secretsmanager
)
from constructs import Construct

from app.vpc_stack import VpcStack


class ECSEc2DeploymentStack(Stack):
    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            vpc_stack: VpcStack,
            env_name: str,
            **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.environment_name = env_name
        self.ecs_vpc = vpc_stack.vpc
        self.ecs_sg = self.ecs_vpc.ec2_sg
        #self.fix_security_group()
        self.ecs_role = iam.Role()
        self.fix_iam_role()
        self.ecs_auto_scaling = autoscaling.AutoScalingGroup()
        self.fix_auto_scaling()
        asg_capacity_provider = ecs.AsgCapacityProvider(self, "AsgCapacityProvider",
           auto_scaling_group=self.ecs_auto_scaling,
           enable_managed_scaling=True,
           enable_managed_termination_protection=False,
           capacity_provider_name="DefaultAsgCapacityProvider"
        )

        self.esc_cluster = ecs.Cluster(self, "ECSCluster", vpc=self.ecs_vpc)
        self.esc_cluster.add_asg_capacity_provider(asg_capacity_provider)
        self.ecr_repo = ecr.Repository(self, "ECRRepository")

        config = self.load_configuration()

        environment = self.prepare_environment(config)
        secrets = self.prepare_secrets(config)

        self.namespace = sd.PrivateDnsNamespace(
            self, "ServiceDiscoveryNamespace",
            name="myapp.local",
            vpc=self.ecs_vpc
        )

        self.task_definition = ecs.Ec2TaskDefinition(self, "SpringBootTask")

        self.task_definition.add_container(
            "SpringBootContainer",
            image=ecs.ContainerImage.from_ecr_repository(self.ecr_repo),
            memory_limit_mib=512,
            environment=environment,
            secrets=secrets,
            port_mappings=[ecs.PortMapping(container_port=8080, host_port=80)]
        )

        self.ecs_service = ecs.Ec2Service(
            self, "SpringBootService",
            cluster=self.esc_cluster,
            task_definition=self.task_definition,
            cloud_map_options=ecs.CloudMapOptions(
                name="springboot",  # DNS name: springboot.myapp.local
                cloud_map_namespace=self.namespace
            ),
            desired_count=2
        )


    def fix_security_group(self):
        #add ingress rule for the app which runs on port 8080
        self.ecs_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(), ec2.Port.tcp(8080), "allow http"
        )

    def fix_iam_role(self):
        self.ecs_role = iam.Role(self, "ECSInstanceRole",
                 assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
                 managed_policies=[
                     iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerServiceforEC2Role"),
                     iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
                 ]
        )

    def fix_auto_scaling(self):
        launch_template = ec2.LaunchTemplate(
            self, "EcsLaunchTemplate",
            instance_type=ec2.InstanceType("t3.micro"),
            machine_image=ecs.EcsOptimizedImage.amazon_linux2(),
            role=ecs_instance_role,
            user_data=ec2.UserData.custom(self.get_ecs_user_data(cluster.cluster_name)),
            launch_template_name="ecs-instance-template"
        )

        # Auto Scaling Group for ECS EC2 instances
        self.ecs_auto_scaling = autoscaling.AutoScalingGroup(self, "ECSAutoScalingGroup",
                             vpc=self.ecs_vpc,
                             instance_type=ec2.InstanceType("t2.micro"),  #todo: determined(e.g medium for prod and micro for test) based on env_name
                             machine_image=ecs.EcsOptimizedImage.amazon_linux2(),  #todo: parameterized
                             min_capacity=2,  #todo: parameterized
                             max_capacity=2,  #todo: parameterized
                             desired_capacity=2,  #todo: parameterized with default determined from min and max capacity
                             role=self.ecs_role,
                             security_group=self.ecs_sg,
                             launch_template=autoscaling.CfnAutoScalingGroup.LaunchTemplateSpecification(
                                                        LaunchTemplateName=launch_template.launch_template_name,
                                                        Version="$Latest"
                                                        # Using the latest version of the launch template
                             ),
        )

    def load_configuration(self):
        """Load configuration based on environment"""
        env = self.node.try_get_context(self.environment_name) or "dev"
        with open(f"config/{env}.env.json") as f:
            return json.load(f)

    def prepare_environment(self, config):
        """Prepare non-sensitive environment variables"""
        return {
            key: ssm.StringParameter.value_from_lookup(self, value)
            for key, value in config.get("environment", {}).items()
        }

    def prepare_secrets(self, config):
        """Prepare sensitive values from Secrets Manager"""
        return {
            key: ecs.Secret.from_secrets_manager(
                secretsmanager.Secret.from_secret_attributes(self, f"{key}Secret", value)
            )
            for key, value in config.get("secrets", {}).items()
        }

    ###############
    ### secret = secretsmanager.Secret.from_secret_attributes(self, "ImportedSecret",
    ### secret_arn="arn:aws:secretsmanager:<region>:<account-id-number>:secret:<secret-name>-<random-6-characters>",
    ### If the secret is encrypted using a KMS-hosted CMK, either import or reference that key:
    ### encryption_key=encryption_key
    ####)
    ###########