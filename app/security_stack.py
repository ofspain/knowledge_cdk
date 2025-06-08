
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    CfnOutput
)
from constructs import Construct

from app.vpc_stack import VpcStack

from typing import List, Tuple

class EC2Stack(Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc_stack: VpcStack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = vpc_stack.vpc

        self.security_group = ec2.SecurityGroup(
            self, "my_security_group", vpc=self.vpc,
            allow_all_outbound=kwargs.get("allow_all_outbound", True)
        )

        default_ports = {22, 80, 443}
        ports = set(kwargs.get("ports", default_ports))

        # Add any missing default ports
        ports.update(default_ports - ports)

        # Convert back to list if required
        ports = list(ports)

        for port in ports:
            self.security_group.add_ingress_rule(
                ec2.Peer.any_ipv4(), ec2.Port.tcp(port), ""
            )
