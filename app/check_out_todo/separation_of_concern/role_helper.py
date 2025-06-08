from aws_cdk import aws_iam as iam
from constructs import Construct

class TaskRoleHelper:
    def __init__(self, scope: Construct, id: str, services: list[str]):
        self.scope = scope
        self.id = id
        self.services = services
        self.role = self.create_task_role()

    def create_task_role(self) -> iam.Role:
        # Create base role
        role = iam.Role(self.scope, f"{self.id}TaskRole",
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





#  usage

# 1. Import the helper
from your_project.task_role_helper import TaskRoleHelper

# 2. Create Task Role for an app that needs S3 + Secrets Manager + SQS
task_role_helper = TaskRoleHelper(self, "MyApp", services=["s3", "secretsmanager", "sqs"])

# 3. Use the task_role in your Task Definition
task_definition = ecs.Ec2TaskDefinition(self, "TaskDef",
    network_mode=ecs.NetworkMode.AWS_VPC,
    execution_role=task_execution_role,   # the normal ECS infra role
    task_role=task_role_helper.role        # ✅ the app access role
)