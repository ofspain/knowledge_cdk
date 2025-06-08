from aws_cdk import Stack
from constructs import Construct
from pepperize_cdk_vpc import CheapVpc

class CustomisedVpcStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.vpc = CheapVpc(self, "CustomisedVpc")

# https://constructs.dev/packages/@pepperize/cdk-vpc/v/0.0.1112/api/CheapVpc?lang=python