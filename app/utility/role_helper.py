from aws_cdk import aws_iam as iam
from constructs import Construct

class RoleHelper:
    def __init__(self, scope: Construct, id: str, services: list[str]):
        self.scope = scope
        self.id = id
        self.services = services
        self.role = self.create_task_role()

    def create_task_role(self) -> iam.Role:
        # Create base role
        role = iam.Role(self.scope, f"{self.id}_Task_Role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )

        # Attach policies based on requested services
        for service in self.services:
            if service.lower() == "s3":
                role.add_managed_policy(
                    iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess")
                )
            elif service.lower() == "secretsmanager":
                role.add_managed_policy(
                    iam.ManagedPolicy.from_aws_managed_policy_name("SecretsManagerReadWrite")
                )
            elif service.lower() == "sqs":
                role.add_managed_policy(
                    iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSQSFullAccess")
                )
            elif service.lower() == "dynamodb":
                role.add_managed_policy(
                    iam.ManagedPolicy.from_aws_managed_policy_name("AmazonDynamoDBReadOnlyAccess")
                )
            elif service.lower() == "ssm":
                role.add_managed_policy(
                    iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMReadOnlyAccess")
                )
            else:
                raise Exception(f"Unsupported service: {service}")

        return role