# ECS Infra and App Stack Separation

This document outlines the reasoning and structure behind separating infrastructure (infra) and application (app) stacks in an ECS (EC2 launch type) environment.

---

## ✅ Infra Stack Components

The infra stack provides reusable foundational services to support containerized applications.

### 1. **LaunchTemplate**
- **Purpose:** Defines the characteristics and configuration for EC2 instances.
- **Details:**
  - Includes AMI, instance type, user data, security groups, IAM instance profile, etc.
  - Versioned and reusable across ASGs.

### 2. **AutoScalingGroup (ASG)**
- **Purpose:** Manages the scaling behavior and availability of EC2 instances.
- **Details:**
  - Ensures a minimum, maximum, and desired number of instances.
  - Scales based on metrics like CPU, memory, or custom CloudWatch alarms.
  - Serves as the underlying compute for ECS container instances.

### 3. **ECS Cluster**
- **Purpose:** Logical grouping for managing ECS container instances and services.
- **Details:** [MORE...](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ecs/Cluster.html)
  - Hosts containerized tasks or services.
  - Doesn't consume resources directly but acts as a control plane for scheduling.

### 4. **AsgCapacityProvider**
- **Purpose:** Connects ECS with ASG to enable automatic capacity scaling.
- **Details:**
  - Allows ECS to scale EC2 instances based on task demand.
  - ECS can manage ASG lifecycle if "managed scaling" is enabled.
  - Enables multiple capacity providers for mixed instance types or launch strategies.

### ✅ 5. **What CloudWatch Agent Does**
- **Purpose:** If you’ve installed and configured CloudWatch Agent:
- **Details:**
   - It sends system-level logs/metrics (memory %, disk %, /var/log/messages, etc.).
   - These go to the CWAgent namespace and system log groups.



---

## 🏗️ VPC Strategy

- **Approach:** VPC is treated as a global, shared resource (akin to a virtual data center).
- **Justification:**
  - Often provisioned once and reused across multiple stacks.
  - Promotes modularity and network boundary consistency.
  - Needs careful subnet and IP range planning for scalability.

---

## 📦 App Stack Components

The app stack defines services and applications that run on top of the infra stack.

- **ECS Task Definitions:** Describe the containers, environment variables, volumes, and ports.
- **ECS Services:** Manage long-running containers, load balancing, and deployment strategies.
- **Load Balancers (optional):** Handle ingress traffic to ECS services.
- **Service Discovery (optional):** Integrate with Route 53 for internal DNS-based routing.

---

## 🧱 Stack Separation Justification

| Stack      | Purpose                                  | Characteristics                             |
|------------|------------------------------------------|---------------------------------------------|
| **Infra**  | Provides foundational, reusable services | VPC, ASG, LaunchTemplate, ECS Cluster       |
| **App**    | Defines workloads and services           | ECS Services, Task Definitions, ALBs, etc.  |

### Benefits:
- **Modularity:** Changes in one layer don't disrupt the other.
- **Reusability:** Multiple apps can use the same infrastructure.
- **Security & Permissions:** Clear boundary for IAM and CI/CD pipelines.
- **Maintainability:** Easier upgrades and debugging with separation of concerns.

---

## Summary of Components

| Component            | Role in Stack | Description |
|----------------------|----------------|-------------|
| **LaunchTemplate**   | Infra          | EC2 instance configuration template |
| **AutoScalingGroup** | Infra          | Manages scaling of EC2 instances    |
| **ECS Cluster**      | Infra          | Container instance management space |
| **AsgCapacityProvider** | Infra      | Binds ECS to ASG for scaling compute capacity |
| **VPC**              | Shared         | Global network boundary (data center) |

---

# AWS IAM Policies Overview

### 1. **AmazonEC2ContainerServiceforEC2Role**
- **Purpose**: 
  - This is an IAM managed policy typically attached to the EC2 instance profile for ECS container instances.
- **What it does**:
  - Allows the EC2 instance to register itself with an ECS cluster.
  - Enables ECS agent (running on the instance) to communicate with the ECS service.
  - Grants permissions for tasks such as:
    - Pulling container images from **Elastic Container Registry (ECR)**.
    - Publishing logs to **CloudWatch**.
    - Accessing other AWS resources.
- **Summary**: 
  - Think of it as the ECS instance’s "passport" to join and operate within the ECS cluster.

---

### 2. **AmazonSSMManagedInstanceCore**
- **Purpose**: 
  - This is a core policy needed to use AWS Systems Manager (SSM) with an EC2 instance.
- **What it does**:
  - Allows the instance to communicate with the Systems Manager service.
  - Enables features like:
    - **SSM Session Manager** (to connect to the instance without SSH).
    - **Run Command**.
    - **Patch Manager**.
    - **Automation**.
- **Summary**:
  - Essential if you want to manage the instance without opening ports or using bastion hosts.

---

### 3. **CloudWatchAgentServerPolicy**
- **Purpose**: 
  - Grants the permissions needed by the **CloudWatch agent** running on an EC2 instance to collect and send metrics and logs to **Amazon CloudWatch**.
- **What it does**:
  - Lets the CloudWatch agent read instance metadata.
  - Allows publishing of custom logs and metrics to CloudWatch.
  - Typically used to monitor things like:
    - CPU usage.
    - Memory.
    - Disk usage.
    - Application logs.
- **Summary**:
  - Used for monitoring EC2 instances through CloudWatch.
---

## Summary Table

| **Policy Name**                      | **Purpose**                                           | **Attached To**                    |
|--------------------------------------|-------------------------------------------------------|------------------------------------|
| **AmazonEC2ContainerServiceforEC2Role** | ECS container instance registration & operations     | EC2 instance in ECS cluster       |
| **AmazonSSMManagedInstanceCore**      | Enables Systems Manager features                     | Any EC2 instance (SSM-managed)    |
| **CloudWatchAgentServerPolicy**       | Allows CloudWatch Agent to send logs/metrics         | EC2 instance running CloudWatch agent |

# ✅ Application Stack – IAM Roles

These roles are associated with the ECS Tasks and Services that run your application containers.

---

### 1. **ECS Task Execution Role**
- **Attached to**: `TaskDefinition.execution_role`
- **Purpose**:
  ECS uses this role to:
  - Pull container images from **ECR**.
  - Write logs to **CloudWatch**.
  - Fetch secrets from **SSM Parameter Store** or **Secrets Manager**.



### 2. **ECS Task Role**

- **Attached to**: `TaskDefinition.task_role`
  
- **Purpose**:
  
  - This is assumed by your app container at runtime.
  
  - Grants only the permissions your app needs, e.g., access to:
    - **DynamoDB**
    - **S3**
    - **SNS/SQS**
    - **Secrets Manager**
    - External APIs via **VPC endpoints**


## 🧱 Optional But Suggested Roles

| Role                        | Stack     | Needed When                                           |
|-----------------------------|-----------|------------------------------------------------------|
| VPC Flow Logs Role          | Infra     | If you're enabling VPC flow logs to CloudWatch.      |
| CloudWatch Custom Metrics Role | Infra     | If you run CloudWatch agent or collect custom metrics. |
| App-Specific Roles          | App       | Per microservice if different apps need isolation.    |

## 📌 Final Summary

| Role Name                  | In Stack  | Attached To        | Responsibility                                       |
|----------------------------|-----------|--------------------|------------------------------------------------------|
| EcsEc2InstanceRole          | Infra     | EC2 Instance Profile | Join ECS, CW logs, SSM                              |
| AutoScalingServiceRole      | Auto-generated | AWS Service      | Manage EC2 lifecycle                                 |
| EcsServiceLinkedRole        | Auto-generated | AWS ECS         | ECS resource management                             |
| TaskExecutionRole           | App       | TaskDefinition     | Pull images, logs, secrets                          |
| TaskRole                    | App       | TaskDefinition     | App-level AWS access                                 |



```python
task_execution_role = iam.Role(self, "TaskExecutionRole",
    assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
    managed_policies=[
        iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
    ]
)
task_role = iam.Role(self, "AppTaskRole",
    assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
)

# Example policy
task_role.add_managed_policy(
    iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess")
)
```


## ✅ 2. How to Use SSM to Connect to EC2
You're almost there! You already attached the correct role:

```bash
iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
```

## ✅ Checklist to Use SSM Session Manager
🔹 A. SSM Agent is Installed on the EC2 Instance
For Amazon Linux 2 and most modern AMIs, the SSM Agent is pre-installed.

To verify it's running:
```bash
sudo systemctl status amazon-ssm-agent
```

### 🔹 B. EC2 Instance Has Internet Access
This is where PRIVATE_WITH_EGRESS comes into play.

The instance must be able to reach AWS SSM endpoints.

✅ Via NAT Gateway (if in private subnet)

✅ Or via VPC Interface Endpoints for SSM

🔹 C. IAM Role Attached to EC2 Includes the Right Policy
You’ve already done this — ✅

```bash
iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
```
Make sure this role is actually attached to your EC2 instance.

### 🖥️ How to Connect via SSM
🔸 From AWS Console:
Go to EC2 > Instances

Select your instance

Click “Connect”

Choose the “Session Manager” tab

Click Connect

🔸 From AWS CLI:
```bash
aws ssm start-session --target i-xxxxxxxxxxxxxxxxx
```
Replace i-xxxxxxxxxxxxxxxxx with your instance ID.
You must have AWS CLI configured and IAM permissions to use SSM.

### ✅ Summary
You’re doing it right:
Using PRIVATE_WITH_EGRESS + AmazonSSMManagedInstanceCore is the secure and recommended way.

Ensure a NAT Gateway exists (or set up VPC endpoints for SSM).

You don’t need SSH or public IPs when using SSM.


#### APP STACK PROVISIONING

## ✅ Is Boto3 a Python API client?
Yes, Boto3 is the official AWS SDK for Python — it lets Python code interact with AWS services like S3, EC2, Secrets Manager, etc.

"Boto3 client: The AWS Python SDK client used to access AWS services like Secrets Manager."
"Boto3 Secrets Manager client: A Python interface to securely retrieve secrets stored in AWS Secrets Manager."

[BOTO CLIENT DOCS](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager.html)

# Dynamic Configuration & Secrets Management Architecture
### 1. Configuration & Secrets Separation
- AppConfig:
Stores non-sensitive, runtime-tunable configurations (e.g., feature flags, service URLs, toggles).

- Secrets Manager:
Stores sensitive credentials (e.g., DB passwords, API keys, tokens).

Both stores are environment-scoped (e.g., dev, staging, prod) using a standardized hierarchy or naming convention (/env/service/config, /env/service/secret).

### 2. Access Strategy
- ECS Task Definition
References environment-specific parameters indirectly through:

  - IAM roles with scoped permissions

  - Environment variables for resource identifiers (not values)

- Runtime Fetching

  - Use AppConfig Agent (sidecar) preferred for real-time, dynamic updates with minimal app logic.

  - Fallback: Use SDK-based polling in the app code if sidecar pattern is infeasible.

### 3. Update Triggers & Refresh Mechanism
- Trigger-based Fetching:
  - AppConfig Agent listens for changes via AWS AppConfig deployment events or configuration profiles.
  - Secrets Manager fetches only on change — use caching with TTL and automatic refresh (e.g., via AWS SDK wrapper libraries or middleware).

- Application Hot-Reloading:
  - Inject updated config/secrets into running tasks via shared volume, SSM, or environment variable refresh—without requiring full ECS redeploys.



# 🔄 Modern Event-Driven Config & Secret Management (Recommended Update)

- #### AWS AppConfig:
    Stores non-sensitive, runtime-tunable configurations (e.g., feature flags, URLs, toggles), organized by environment (dev, staging, prod) using a consistent hierarchy.

- #### AWS Secrets Manager:
    Stores sensitive credentials (e.g., database passwords, API keys, tokens), also structured per environment for isolation and access control.

  - ##### Amazon ECS Cluster:
      Hosts application containers with each task definition including:

    - App Container: The primary service logic.

    - Sidecar Listener Agent:

        - Subscribes to Amazon SQS or Amazon SNS.

        - Listens for change events triggered by AWS AppConfig or Secrets Manager via Amazon EventBridge.

        - Upon receiving an event:

            - It immediately fetches the updated configuration or secret using AWS SDKs.

            - Updates its local cache.

            - Serves the latest values to the App Container via HTTP (e.g., localhost:2772) or shared volume.




### ⚙️ How Change Detection Works
- CloudTrail logs PutSecretValue, UpdateSecret, StartDeployment, etc.

- EventBridge Rules detect those changes.

- Rules route events to an SNS Topic or SQS Queue.

- The ECS Sidecar Agent subscribes and acts only when a relevant event is received.

This update transforms the configuration pipeline from a pull-based loop to a push-triggered response system, aligning with event-driven architecture principles and delivering a more responsive, efficient, and modern cloud-native system.


### 📈 Advantages Over Polling-Based Approach

| Feature         | Previous (Polling)                            | Updated (Event-Driven via EventBridge)Pushing |
|----------------|-----------------------------------------------|-----------------------------------------------|
| **Efficiency**  | Regular polling regardless of change          | No activity unless change occurs              |
| **Latency**     | Updates may lag until next poll               | Near real-time updates                        |
| **Cost**        | Can incur unnecessary API calls               | Reduces calls, driven by actual change        |
| **Scalability** | Increased overhead with more services         | Scales cleanly with low baseline traffic      |
| **Decoupling**  | Tightly bound to polling intervals            | Cleanly reacts to real system events          |
| **Security**    | Possible overexposure via constant calls      | Controlled, event-triggered access            |


### ✅ 4. **Logging Application Log to CloudWatch**

Define a log group for your application to be attached to your task definition
```python
log_group = logs.LogGroup(
    self,
    "AppLogGroup",
    retention=logs.RetentionDays.ONE_WEEK,
    log_group_name=f"/ecs/{self.env}-your-app"
)
```
Use the log group in your container in the task definition
```python
task_definition = ecs.Ec2TaskDefinition(self, "AppTaskDef")

container = task_definition.add_container(
    "AppContainer",
    image=ecs.ContainerImage.from_registry("amazon/amazon-ecs-sample"),
    memory_limit_mib=512,
    logging=ecs.LogDriver.aws_logs(
        stream_prefix="your-app",
        log_group=log_group
    )
)
```
Required Role
ECS EC2 instance roles don’t need special permissions beyond 
*AmazonEC2ContainerServiceforEC2Role*, which you've already attached. This includes permissions to write logs via the ECS agent.

# 🔄 ACCESSING IMAGE FROM REPOSITORY
### ✅ Choose One of These Two Approaches:
#### Option 1: Use Pre-Built Image via image_uri (CI/CD pipeline)
This is best when:
- You build and push Docker images in a pipeline
- The image URI is passed in (e.g. "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app:latest")

```python
self.image_uri = image_uri

container_image = ecs.ContainerImage.from_registry(self.image_uri)

# Use in container definition
self.task_definition.add_container(
    self.app_name + "Container",
    image=container_image,
    ...
)
```
**🔥 Simple. Clean. No ECR repo created by CDK.**

#### Option 2: Build Image During CDK Deploy (using Docker context)
Use this only if:
- You want CDK to build your Docker image from source code during cdk deploy
- You’re okay with the slower deploys and tighter CDK/image coupling
```python
from aws_cdk.aws_ecr_assets import DockerImageAsset

image_asset = DockerImageAsset(self, "AppImage",
    directory="./path-to-your-docker-context"  # e.g., "./app"
)

container_image = ecs.ContainerImage.from_docker_image_asset(image_asset)

self.task_definition.add_container(
    self.app_name + "Container",
    image=container_image,
    ...
)
```
**🔥 More Complicated!! This auto-creates a repo and uploads the image.**

## DEPLOYING USING from_look_up
### ✅ TL;DR: What’s best for production?
🔒 In production, you should explicitly hardcode or parameterize the environment (account and region) in your CDK stack.
Avoid relying on CDK_DEFAULT_ACCOUNT / CDK_DEFAULT_REGION in production — those are useful for development but can lead 
to non-deterministic behavior in CI/CD pipelines or shared environments.

#### ✅ Recommended Best Practices for Production
✅ 1. Explicit env in cdk.Environment(...)
Hardcode or inject the correct values per environment (dev, staging, prod):
```python
env=cdk.Environment(
    account="123456789012",
    region="us-west-2"
)
```

```json
{
  "context": {
    "envs": {
      "dev": {
        "account": "111111111111",
        "region": "us-west-2"
      },
      "prod": {
        "account": "222222222222",
        "region": "us-east-1"
      }
    }
  }
}
```

# LOGGING AND OBSERVABILITY
### Comparative Overview: CloudWatch Logs vs S3 for VPC Flow Logs
| Feature                         | **CloudWatch Logs**                                      | **S3**                                                  |
| ------------------------------- | -------------------------------------------------------- | ------------------------------------------------------- |
| **Ease of Setup**               | Easier — direct integration with `ec2.FlowLog`           | Slightly more involved, but still supported natively    |
| **Query Support**               | **CloudWatch Logs Insights** — real-time, ad-hoc queries | No native querying — requires Athena or external tools  |
| **Latency (Real-Time Access)**  | Near real-time                                           | Delayed (files are batched and written every 5–15 mins) |
| **Retention Control**           | Fine-grained, configurable in days                       | Lifecycle policies in S3 (less granular)                |
| **Storage Cost**                | Higher (esp. at scale with Insights usage)               | Lower long-term cost                                    |
| **Integration with 3rd Parties**| Requires export or subscription filters                  | Easier — S3 is a common input for many analytics tools  |

##### to s3
```python
  bucket = s3.Bucket(self, "VpcFlowLogsBucket",
    removal_policy=RemovalPolicy.DESTROY,
    auto_delete_objects=True  # for dev/test environments
)

ec2.FlowLog(self, "VpcFlowLogToS3",
    resource_type=ec2.FlowLogResourceType.from_vpc(vpc),
    destination=ec2.FlowLogDestination.to_s3(bucket)
)
```
##### to log group
```python
vpc = ec2.Vpc.from_lookup(self, "ImportedVPC", vpc_id=shared_vpc_id)

log_group = logs.LogGroup(self, "VpcFlowLogsGroup",
    retention=logs.RetentionDays.ONE_WEEK
)

ec2.FlowLog(self, "VpcFlowLog",
    resource_type=ec2.FlowLogResourceType.from_vpc(vpc),
    destination=ec2.FlowLogDestination.to_cloud_watch_logs(log_group)
)
```

### Optional: Export to Elasticsearch (OpenSearch or Self-hosted)
If you're staying independent of AWS-native analytics and want to send logs to an 
Elasticsearch index (e.g. in Elastic Cloud, or self-hosted), here’s how you can do that:
#### Option A: S3 → Logstash → Elasticsearch
- Log flow logs to S3 (as shown above)
- Set up Logstash with an S3 input and Elasticsearch output
- Deploy Logstash (can be on EC2, Docker, EKS, etc.)

logstash.conf
```flow js
input {
  s3 {
    bucket => "your-vpc-logs-bucket"
    region => "us-east-1"
    prefix => "AWSLogs/"
    access_key_id => "<your-access-key>"
    secret_access_key => "<your-secret>"
  }
}

filter {
  # Optionally parse the VPC Flow Log format here
}

output {
  elasticsearch {
    hosts => ["http://your-elasticsearch-host:9200"]
    index => "vpc-flow-logs-%{+YYYY.MM.dd}"
  }
}
```

#### Option B: Lambda Function Triggered by S3 Event
You can write a Lambda function that triggers on new S3 objects (flow logs), 
parses the data, and pushes it to Elasticsearch via the REST API.

This gives you fine-grained control but is more complex to manage.

```python
from aws_cdk import (
    aws_ec2 as ec2,
    aws_s3 as s3,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_events,
    core,
)

class VpcFlowLogsToEsStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, *, vpc_id: str, es_endpoint: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Import existing VPC
        vpc = ec2.Vpc.from_lookup(self, "Vpc", vpc_id=vpc_id)

        # Create S3 bucket for flow logs
        flow_logs_bucket = s3.Bucket(self, "FlowLogsBucket",
            removal_policy=core.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Create VPC Flow Log to S3
        ec2.FlowLog(self, "VpcFlowLogToS3",
            resource_type=ec2.FlowLogResourceType.from_vpc(vpc),
            destination=ec2.FlowLogDestination.to_s3(flow_logs_bucket)
        )

        # Lambda Role & Policy
        lambda_role = iam.Role(self, "FlowLogsProcessorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )
        lambda_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"))

        # Allow Lambda to read from S3 bucket
        flow_logs_bucket.grant_read(lambda_role)

        # You will need to add permissions to Lambda for Elasticsearch, usually via network config or VPC Endpoint if ES is inside a VPC

        # Lambda function code (replace with your actual implementation)
        fn = _lambda.Function(self, "FlowLogsToEsFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            role=lambda_role,
            code=_lambda.Code.from_asset("lambda/flow_logs_to_es"),  # local path to your Lambda code
            environment={
                "ES_ENDPOINT": es_endpoint
            }
        )

        # Trigger Lambda on new S3 objects
        fn.add_event_source(lambda_events.S3EventSource(
            flow_logs_bucket,
            events=[s3.EventType.OBJECT_CREATED]
        ))
```

# LAMBDA
### ✅ A) Lambda with Public Configuration (No VPC)
This is the simplest form — Lambda has outbound internet access by default.
```python
from aws_cdk import (
    aws_lambda as lambda_,
    aws_iam as iam,
    Stack,
)
from constructs import Construct
import os

class PublicLambdaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Create role with DynamoDB access
        lambda_role = iam.Role(self, "PublicLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonDynamoDBReadOnlyAccess")
        )

        # Define the function
        lambda_.Function(self, "PublicLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda"),  # assumes `lambda/index.py` exists
            role=lambda_role,
        )
```
🔁 The function can directly talk to DynamoDB over the internet — no extra networking needed.

### ✅ B) Lambda Deployed Inside a VPC (with DynamoDB access)
This example includes:
- A VPC
- A private subnet (no internet)
- A Lambda inside that subnet
- A VPC interface endpoint for DynamoDB, so the Lambda can access DynamoDB privately

```python
from aws_cdk import (
    aws_lambda as lambda_,
    aws_ec2 as ec2,
    aws_iam as iam,
    Stack
)
from constructs import Construct

class VpcLambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Create a VPC with private subnets only
        vpc = ec2.Vpc(self, "LambdaVpc",
            max_azs=2,
            nat_gateways=0,  # no internet access
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24
                )
            ]
        )

        # Add VPC endpoint for DynamoDB
        vpc.add_interface_endpoint("DynamoDbEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.DYNAMODB,
            private_dns_enabled=True,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[]  # optional SG for endpoint
        )

        # IAM Role for Lambda
        lambda_role = iam.Role(self, "PrivateLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole")
        )
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonDynamoDBReadOnlyAccess")
        )

        # Lambda inside the VPC
        lambda_.Function(self, "PrivateLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            role=lambda_role
        )

```







