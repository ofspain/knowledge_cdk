## ✅ Objective Recap
You're running:
- ECS (on EC2, not Fargate)
- Application: Behind a self-managed reverse proxy (custom NGINX) on a dedicated EC2 instance
- Goal: Auto-scale ECS Auto Scaling Group (ASG) based on the number of pending requests
- Approach: Push a custom CloudWatch metric, then use target tracking or step scaling based on that metric

## 🧠 Where to Collect the Pending Request Metric?

### Option 1: Inside the application ECS task
- Pros:

  - Knows the real, app-level pending request count

  - More precise if "pending" means app queue, async backlog, or unprocessed items

- Cons:

  - Distributed across ECS tasks — requires aggregation

  - Difficult to consolidate into one metric unless each task pushes to CloudWatch separately with dimensions, or you use a sidecar agent

### Option 2: From the NGINX proxy (outside ECS)
- Pros:
  - Single point of ingress = single place to track backlog (e.g., NGINX $connections_waiting)

  - Easier to collect, centralize, and push as one metric

- Cons:

  - May not reflect actual app backlog — just pending connections or requests in queue

  - May miss internal app-level queuing/delays

## ✅ Recommendation:
If your definition of "pending requests" = requests accepted but not yet processed, and if your app has visibility into the queue, then collect from the app.

If you’re okay with proxy-side heuristics (e.g., connection backlog), then NGINX metrics are easier and centralized.
#### SUMMARY
| Metric Source    | Best for                         |
| ---------------- | -------------------------------- |
| ECS app/task     | Precise internal backlog         |
| Custom NGINX EC2 | General traffic/backlog proxying |


## 🛠️ CDK Python: Implementing Custom Metric-Based Auto Scaling
Assuming:

You already have an AutoScalingGroup created for ECS capacity provider

You're publishing a custom metric like:
Namespace="MyApp", MetricName="PendingRequests"

#### 🔧 1. Create the Auto Scaling Policy

```python
from aws_cdk import (
    aws_autoscaling as autoscaling,
    aws_cloudwatch as cloudwatch,
    Stack,
)
from constructs import Construct

class AsgScalingStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Assuming this ASG is tied to your ECS capacity provider
        asg = autoscaling.AutoScalingGroup.from_auto_scaling_group_name(
            self, "MyAsg", auto_scaling_group_name="your-asg-name"
        )

        # Custom CloudWatch Metric (must match what your app or agent pushes)
        pending_requests_metric = cloudwatch.Metric(
            namespace="MyApp",
            metric_name="PendingRequests",
            statistic="Average",
            period=cloudwatch.Duration.minutes(1)
        )

        # Add Target Tracking Scaling Policy
        asg.scale_on_metric("ScaleOnPendingRequests",
            metric=pending_requests_metric,
            scaling_steps=[
                autoscaling.ScalingInterval(upper=50, change=-1),  # scale in if < 50
                autoscaling.ScalingInterval(lower=100, change=+1), # scale out if > 100
                autoscaling.ScalingInterval(lower=200, change=+2), # scale out more
            ],
            adjustment_type=autoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            cooldown=cdk.Duration.minutes(2),
            estimated_instance_warmup=cdk.Duration.minutes(3)
        )
```

## ✅ Other Considerations
- IAM permissions: Your ECS tasks or NGINX EC2 need cloudwatch:PutMetricData permissions.
- Dimension strategy: You can use dimensions (e.g., InstanceId) to push per-source metrics and then use CloudWatch math/alarms.
- ASG link to ECS: Ensure the ASG is registered as an ECS Capacity Provider with managed scaling disabled (CDK can handle this too if needed).

## ✅ 1. Configure CloudWatch Agent on Your NGINX EC2
Step-by-step:
- Install the agent:
```bash
sudo yum install amazon-cloudwatch-agent -y  # for Amazon Linux
```
- Create a config file:

Here’s a minimal example (cloudwatch-agent-config.json) to push a custom metric from a script/log:
```json
{
  "metrics": {
    "metrics_collected": {},
    "append_dimensions": {
      "InstanceId": "${aws:InstanceId}"
    }
  }
}
```

- Start the agent
```bash
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -c file:/path/to/cloudwatch-agent-config.json \
  -s
```

## ✅ 2. Python Script to Push Custom Metric (PutMetricData)
```python
import boto3
import datetime

cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')  # adjust region

def publish_pending_requests(count):
    cloudwatch.put_metric_data(
        Namespace='MyApp',
        MetricData=[
            {
                'MetricName': 'PendingRequests',
                'Timestamp': datetime.datetime.utcnow(),
                'Value': count,
                'Unit': 'Count',
                'Dimensions': [
                    {'Name': 'Service', 'Value': 'nginx'}
                ]
            }
        ]
    )

# Example usage
publish_pending_requests(count=23)
```
#### Permission Needed
Attach an IAM role or instance profile with:
```json
{
  "Effect": "Allow",
  "Action": "cloudwatch:PutMetricData",
  "Resource": "*"
}
```

## FURTHER WORK
Let me know if you'd prefer the metric to be scraped from NGINX logs/status or generated from another source (like /var/log/nginx/access.log or the stub status module).
Let me know if you want help wiring this into a systemd timer or cron job, or containerizing it as a monitoring sidecar.
