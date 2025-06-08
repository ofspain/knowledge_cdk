from aws_cdk import Stack, aws_ec2 as ec2, aws_iam as iam, aws_ecs as ecs, aws_autoscaling as autoscaling
from constructs import Construct

class ECSClusterStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.vpc = ec2.Vpc(self, "Vpc", max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="PublicSubnet", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="PrivateSubnet", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24)
            ]
        )

        self.security_group = ec2.SecurityGroup(self, "EcsSecurityGroup", vpc=self.vpc, allow_all_outbound=True)
        self.security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(8080), "Allow app traffic")

        self.ec2_role = iam.Role(self, "EcsEc2InstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerServiceforEC2Role"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ]
        )

        self.launch_template = ec2.LaunchTemplate(self, "EcsLaunchTemplate",
            instance_type=ec2.InstanceType("t3.micro"),
            machine_image=ecs.EcsOptimizedImage.amazon_linux2(),
            role=self.ec2_role,
            security_group=self.security_group
        )

        self.auto_scaling_group = autoscaling.AutoScalingGroup(self, "EcsAutoScalingGroup",
            vpc=self.vpc, min_capacity=2, max_capacity=4, desired_capacity=2,
            launch_template=self.launch_template,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )

        self.cluster = ecs.Cluster(self, "EcsCluster", vpc=self.vpc, container_insights=True)

        self.capacity_provider = ecs.AsgCapacityProvider(self, "AsgCapacityProvider",
            auto_scaling_group=self.auto_scaling_group, enable_managed_scaling=True
        )
        self.cluster.add_asg_capacity_provider(self.capacity_provider)
