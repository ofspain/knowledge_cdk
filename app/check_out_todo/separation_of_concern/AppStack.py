from aws_cdk import Stack, aws_ecs as ecs, aws_ecs_patterns as ecs_patterns
from constructs import Construct

class ECSAppStack(Stack):
    def __init__(self, scope: Construct, id: str, cluster, image_uri, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define ECS Task Definition
        task_definition = ecs.FargateTaskDefinition(self, "AppTaskDef")
        container = task_definition.add_container("AppContainer",
            image=ecs.ContainerImage.from_registry(image_uri),
            memory_limit_mib=512,
            cpu=256
        )
        container.add_port_mappings(ecs.PortMapping(container_port=8080))

        # Create ECS Service
        self.service = ecs_patterns.ApplicationLoadBalancedFargateService(self, "EcsService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=2
        )
