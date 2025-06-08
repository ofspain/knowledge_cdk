from aws_cdk import ( Stack, CfnOutput)
from constructs import Construct

import aws_cdk.aws_iam as iam

class IAMRoleStack(Stack):
    def __init__(self, scope: Construct, role_id: str, roles: list[str], entity: str, **kwargs):
        super().__init__(scope, role_id, **kwargs)

        self.entity = entity
        self.roles = roles

        self.fix_entity()

        # Create an IAM Role for EC2
        self.ec2_role = iam.Role(
            self, "MyEC2Role",
            assumed_by=iam.ServicePrincipal(self.entity),  # EC2 will assume this role
            description="IAM Role for access AWS services"
        )

        # Add permissions (Policies)
        # ec2_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))
        # ec2_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("SecretsManagerReadWrite"))

        self.attach_roles()

        CfnOutput(self, "IAMRoleName", value=self.ec2_role.role_name)

    def fix_entity(self):
        if None == self.entity:
            self.entity = "ec2.amazonaws.com"

    def attach_roles(self):
        for role in self.roles:
            self.ec2_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name(role))


