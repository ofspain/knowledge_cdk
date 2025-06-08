import boto3
import json
import os

# Initialize AWS clients
s3 = boto3.client('s3')
secretsmanager = boto3.client('secretsmanager')
ecs = boto3.client('ecs')

# Environment variables passed to Lambda (set in CDK)
CLUSTER_NAME = os.environ['CLUSTER_NAME']
SERVICE_NAME = os.environ['SERVICE_NAME']
CONTAINER_NAME = os.environ['CONTAINER_NAME']
TASK_ROLE_ARN = os.environ['TASK_ROLE_ARN']
EXECUTION_ROLE_ARN = os.environ['EXECUTION_ROLE_ARN']
TASK_FAMILY = os.environ['TASK_FAMILY']


def load_config_from_s3(bucket, key):
    """Load the configuration file from S3."""
    response = s3.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')
    return json.loads(content)


def get_secret_arn(secret_name):
    """Retrieve the full ARN of a secret given its name."""
    response = secretsmanager.describe_secret(SecretId=secret_name)
    return response['ARN']


def lambda_handler(event, context):
    """Lambda entry point."""
    print(f"Received event: {json.dumps(event)}")

    # Event structure based on S3 PUT trigger
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    # Load the config
    config = load_config_from_s3(bucket, key)

    # Prepare environment variables
    environment_vars = [
        {"name": k, "value": v}
        for k, v in config.get('environment', {}).items()
    ]

    # Prepare secrets
    secrets_list = []
    for secret in config.get('secrets', []):
        secret_name = secret['secret_name']
        resource_name = secret['resource']

        secret_arn = get_secret_arn(secret_name)

        secrets_list.append({
            "name": f"{resource_name.upper()}_SECRET",
            "valueFrom": secret_arn
        })

    # Fetch the current task definition
    service_response = ecs.describe_services(
        cluster=CLUSTER_NAME,
        services=[SERVICE_NAME]
    )
    task_definition_arn = service_response['services'][0]['taskDefinition']

    task_definition = ecs.describe_task_definition(
        taskDefinition=task_definition_arn
    )['taskDefinition']

    container_definitions = task_definition['containerDefinitions']

    # Update the correct container definition
    for container in container_definitions:
        if container['name'] == CONTAINER_NAME:
            container['environment'] = environment_vars
            container['secrets'] = secrets_list

    # Register new task definition revision
    register_response = ecs.register_task_definition(
        family=TASK_FAMILY,
        networkMode=task_definition['networkMode'],
        containerDefinitions=container_definitions,
        requiresCompatibilities=task_definition['requiresCompatibilities'],
        cpu=task_definition.get('cpu'),
        memory=task_definition.get('memory'),
        executionRoleArn=EXECUTION_ROLE_ARN,
        taskRoleArn=TASK_ROLE_ARN,
        volumes=task_definition.get('volumes', []),  # Carry forward volumes if any
    )

    new_task_definition_arn = register_response['taskDefinition']['taskDefinitionArn']

    print(f"New task definition registered: {new_task_definition_arn}")

    # Update ECS service to use the new task definition
    ecs.update_service(
        cluster=CLUSTER_NAME,
        service=SERVICE_NAME,
        taskDefinition=new_task_definition_arn,
        forceNewDeployment=True  # Forces tasks to restart
    )

    print("Service updated successfully and new deployment started.")
