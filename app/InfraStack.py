import base64
import json

from aws_cdk import (
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_logs as logs,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_ecs as ecs,
    aws_autoscaling as autoscaling,
    CfnOutput, Duration
)
from constructs import Construct
from app.vpc_stack import VpcStack



def get_user_data(meta_data:dict[str,object]) -> ec2.UserData:
    user_data = ec2.UserData.for_linux()
    user_data.add_commands(
        "yum install -y amazon-cloudwatch-agent",
        "mkdir -p /opt/aws/amazon-cloudwatch-agent/etc/"
    )

    user_data.add_commands(
        f'echo \'{json.dumps(cloudwatch_config)}\' > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json',
        "/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s"
    )


# Create CloudWatch Agent configuration file (memory, disk, etc.)
cloudwatch_config = {
    "agent": {
        "metrics_collection_interval": 60,
        "run_as_user": "root"
    },
    "metrics": {
        "append_dimensions": {
            "InstanceId": "${aws:InstanceId}"
        },
        "metrics_collected": {
            "mem": {
                "measurement": [
                    "mem_used_percent"
                ],
                "metrics_collection_interval": 60
            },
            "disk": {
                "measurement": [
                    "used_percent"
                ],
                "metrics_collection_interval": 60,
                "resources": [
                    "/"
                ]
            }
        }
    }
}

class InfraStack(Stack):
    def __init__(self, scope: Construct, stack_id: str, vpc_stack: VpcStack, app_ports: [], environment_name: str, **kwargs):
        super().__init__(scope, stack_id, **kwargs)

        self.environment_name = environment_name
        self.vpc = vpc_stack.vpc
        self.security_group = vpc_stack.ec2_sg

        # note while the below returns None when variable is not returned and get_context(...) raises an exception when variable is not defines
        # self.env = self.node.try_get_context(environment_name) or "dev"

        [self.security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(p), f"Allow traffic on port {p}") for p
         in app_ports]

        self.ec2_role = iam.Role(self, "EcsEc2InstanceRole",
               assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
               managed_policies=[
                 iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerServiceforEC2Role"),
                 iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                 iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy")
               ]
        )

        ec2_features = self.ec2_features()
        user_data = get_user_data({})
        # self.launch_template = ec2.LaunchTemplate(self, "EcsLaunchTemplate",
        #            instance_type=ec2.InstanceType(ec2_features.get("type", self.instance_types(self.environment_name))), # base this on env or default to t3.micro
        #            machine_image=ecs.EcsOptimizedImage.amazon_linux2(),
        #            role=self.ec2_role,
        #            security_group=self.security_group,
        #            user_data=user_data
        # )
        #
        # # A Fleet that represents a managed set of EC2 instances.
        # self.auto_scaling_group = autoscaling.AutoScalingGroup(self, "EcsAutoScalingGroup",
        #            vpc=self.vpc,
        #            min_capacity=ec2_features.get("min_capacity", 1),
        #            max_capacity=ec2_features.get("max_capacity", 2),
        #            desired_capacity=ec2_features.get("desired_capacity", 1),
        #            launch_template=self.launch_template,
        #            vpc_subnets=ec2.SubnetSelection(
        #               subnets=self.vpc.public_subnets
        #            ),
        #
        #            #to lockdown, check note
        #            # vpc_subnets=ec2.SubnetSelection(
        #            #    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        # )

        self.auto_scaling_group = autoscaling.AutoScalingGroup(self, "EcsAutoScalingGroup",
                vpc=self.vpc,
                instance_type=ec2.InstanceType(ec2_features.get("type", self.instance_types())),
                machine_image=ecs.EcsOptimizedImage.amazon_linux2(),
                role=self.ec2_role,
                security_group=self.security_group,
                user_data=user_data,
                min_capacity=ec2_features.get("min_capacity", 1),
                max_capacity=ec2_features.get("max_capacity", 2),
                desired_capacity=ec2_features.get("desired_capacity", 1),
                vpc_subnets=ec2.SubnetSelection(
                    subnets=self.vpc.public_subnets
                    # Or, if locking down:
                    # subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                )
        )

        self.add_target_tracking_scaling(name="App", target_cpu_utilization=50)

        self.cluster = ecs.Cluster(self, "EcsCluster", cluster_name="ecs-cluster."+self.environment_name,
                                   vpc=self.vpc, container_insights=True)

        self.capacity_provider = ecs.AsgCapacityProvider(self, "AsgCapacityProvider",
                                                         auto_scaling_group=self.auto_scaling_group,
                                                         enable_managed_scaling=True
                                                         )
        self.cluster.add_asg_capacity_provider(self.capacity_provider)


        # Create a CloudWatch alarm for CPU Utilization and potentially write to an sns topic

        # topic = sns.Topic(
        #     self, "MySnsTopic",
        #     topic_name="cpu_alarm_topic"
        # )
        #
        # # Subscribe email to the topic
        # topic.add_subscription(
        #     subscriptions.EmailSubscription("example@gmail.com")
        # )

        # Placeholder: create or import your AutoScaling policy
        # increase_policy = autoscaling.CfnScalingPolicy(
        #     self, "IncreaseEC2Policy",
        #     auto_scaling_group_name="your-asg-name",  # Replace with actual ASG name
        #     policy_type="SimpleScaling",
        #     adjustment_type="ChangeInCapacity",
        #     scaling_adjustment=1,
        #     cooldown='300',
        # )

        # Increase EC2 alarm
        cloudwatch.Alarm(
            self, "IncreaseEC2Alarm",
            alarm_name="increase-ec2-alarm",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            evaluation_periods=2,
            metric=cloudwatch.Metric(
                namespace="AWS/EC2",
                metric_name="CPUUtilization",
                statistic="Average",
                period=Duration.seconds(120),
                # note this is necessary for logging to cloudwatch rather than a topic
                dimensions_map={
                    "AutoScalingGroupName": self.auto_scaling_group.auto_scaling_group_name
                }
            ),
            threshold=70,
            alarm_description="This metric monitors ec2 cpu utilization, if it goes above 70% for 2 periods it will trigger an alarm.",
            ## for loging into a topic
            # alarm_actions=[
            #     topic.topic_arn,
            #     increase_policy.ref  # This will resolve to the ARN at deploy time
            # ],
        )

        # Reduce EC2 alarm
        cloudwatch.Alarm(
            self, "ReduceEC2Alarm",
            alarm_name="reduce-ec2-alarm",
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_OR_EQUAL_TO_THRESHOLD,
            evaluation_periods=2,
            metric=cloudwatch.Metric(
                namespace="AWS/EC2",
                metric_name="CPUUtilization",
                statistic="Average",
                period=Duration.seconds(120),
                # note this is necessary for logging to cloudwatch rather than a topic
                dimensions_map = {
                    "AutoScalingGroupName": self.auto_scaling_group.auto_scaling_group_name
                }
            ),
            threshold=40,
            alarm_description="This metric monitors ec2 cpu utilization, if it goes below 40% for 2 periods it will trigger an alarm.",
            ## log to a topic
            # alarm_actions=[
            #     topic.topic_arn,
            #     increase_policy.ref  # Note: same policy as above (per Terraform)
            # ],
        )

        CfnOutput(
            self, "ClusterName",
            value=self.cluster.cluster_name
        )

    def instance_types(self) -> str:
        return {
            "prod": "t2.micro",
            "dev": "t2.micro",
            "test": "t3.micro"
        }.get(self.environment_name, "t3.micro")

    def add_target_tracking_scaling(self,
                                    name: str,
                                    target_cpu_utilization: int = 50,
                                    disable_scale_in: bool = False,
                                    cooldown_minutes: int = 5) -> None:
        """
        Adds a CPU-based target tracking scaling policy to the AutoScalingGroup.
        """
        self.auto_scaling_group.scale_on_cpu_utilization(
            id=f"{name}TargetTrackingPolicy",
            target_utilization_percent=target_cpu_utilization,
            cooldown=Duration.minutes(cooldown_minutes),
            disable_scale_in=disable_scale_in,
          #  policy_name=f"{name}CpuTargetTracking"
        )

    def ec2_features(self):
        if self.environment_name == "production":
            return {
                "type": "m5.large",
                "min_capacity": 3,
                "max_capacity": 10,
                "desired_capacity": 5
            }
        else:
            return {
                "type": "t2.micro",
                "min_capacity": 1,
                "max_capacity": 2,
                "desired_capacity": 1
            }