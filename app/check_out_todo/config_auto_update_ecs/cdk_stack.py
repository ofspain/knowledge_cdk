from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_s3_notifications as s3n,
)
from constructs import Construct

class ConfigUpdateStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # 1. Create S3 bucket
        config_bucket = s3.Bucket(
            self, "ConfigBucket",
            versioned=True,
            removal_policy=cdk.RemovalPolicy.DESTROY,  # For demo (use RETAIN in production)
            auto_delete_objects=True  # Only for testing
        )

        # 2. Create Lambda function
        config_update_lambda = _lambda.Function(
            self, "ConfigUpdateLambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambda"),  # path to Lambda code
            environment={
                "CLUSTER_NAME": "your-ecs-cluster",
                "SERVICE_NAME": "your-ecs-service",
                "CONTAINER_NAME": "your-container-name",
                "TASK_ROLE_ARN": "your-task-role-arn",
                "EXECUTION_ROLE_ARN": "your-execution-role-arn",
                "TASK_FAMILY": "your-task-family",
            },
            timeout=cdk.Duration.seconds(300),
        )

        # 3. Grant permissions to Lambda
        config_bucket.grant_read(config_update_lambda)

        config_update_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ecs:DescribeServices",
                    "ecs:DescribeTaskDefinition",
                    "ecs:RegisterTaskDefinition",
                    "ecs:UpdateService",
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=["*"],  # Or narrow down if you want
            )
        )

        # 4. Add S3 notification to trigger Lambda
        notification = s3n.LambdaDestination(config_update_lambda)
        config_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED, notification
        )
