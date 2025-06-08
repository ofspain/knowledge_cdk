from constructs import Construct
from aws_cdk import  (Stack, Duration, CfnOutput)
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_lambda as _lambda
import aws_cdk.aws_iam as iam
import aws_cdk.aws_s3_notifications as s3_notifications

class LambdaAutoDeployStack(Stack):
    def __init__(self, scope: Construct, stack_id: str, **kwargs):
        super().__init__(scope, stack_id, **kwargs)

        #  Create an S3 Bucket to store Lambda ZIP files
        bucket = s3.Bucket(self, "LambdaStorageBucket")

        #  IAM Role for Deployment Lambda
        lambda_role = iam.Role(
            self, "LambdaDeploymentRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSLambda_FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        #  Auto-Deploy Lambda Function
        deploy_lambda_code = """
            import boto3
            import os

            s3_client = boto3.client("s3")
            lambda_client = boto3.client("lambda")

            def lambda_handler(event, context):
                for record in event["Records"]:
                    bucket_name = record["s3"]["bucket"]["name"]
                    file_key = record["s3"]["object"]["key"]

                    if not file_key.endswith(".py"):
                        print(f"Skipping non-Python file: {file_key}")
                        continue  # Ignore non-Python files

                    function_name = file_key.replace(".py", "")

                    try:
                        # Check if function already exists
                        response = lambda_client.get_function(FunctionName=function_name)

                        # If it exists, update the code
                        lambda_client.update_function_code(
                            FunctionName=function_name,
                            S3Bucket=bucket_name,
                            S3Key=file_key
                        )
                        print(f"Lambda {function_name} updated.")

                    except lambda_client.exceptions.ResourceNotFoundException:
                        # If it doesn't exist, create the Lambda function
                        lambda_client.create_function(
                            FunctionName=function_name,
                            Runtime="python3.9",
                            Role=os.environ["LAMBDA_ROLE_ARN"],
                            Handler=f"{function_name}.lambda_handler",  # Python module must match file name
                            Code={"S3Bucket": bucket_name, "S3Key": file_key},
                            Timeout=300,
                            MemorySize=128
                        )
                        print(f"Lambda {function_name} created.")
        """

        # Auto deploy the inline lambda function
        deploy_lambda = _lambda.Function(
            self, "AutoDeployLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_inline(deploy_lambda_code),
            timeout=Duration.minutes(5),
            role=lambda_role,
            environment={
                "LAMBDA_ROLE_ARN": lambda_role.role_arn  # Allow Lambda to create functions
            }
        )

        # 🔥 S3 Bucket triggers the Deploy Lambda when a ZIP file is uploaded
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3_notifications.LambdaDestination(deploy_lambda)
        )

        # Outputs
        CfnOutput(self, "S3BucketName", value=bucket.bucket_name)
        CfnOutput(self, "AutoDeployLambdaName", value=deploy_lambda.function_name)
