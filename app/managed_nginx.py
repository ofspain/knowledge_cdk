from typing import Dict

from aws_cdk import (
    aws_ec2 as ec2,
    Stack,
    CfnOutput,
    aws_ssm as ssm,
)
from constructs import Construct


def get_user_data(dns: str) -> ec2.UserData:
    user_data = ec2.UserData.custom(
        f"""#!/bin/bash
        sudo yum update -y
        sudo amazon-linux-extras enable nginx1
        sudo yum install -y nginx
        sudo systemctl start nginx
        sudo systemctl enable nginx
        echo '<html><body><h1>Maintenance Mode</h1><p>The application is currently unavailable. Please try again later.</p></body></html>' | sudo tee /usr/share/nginx/html/maintenance.html

        echo 'upstream ecs_backend {{
            least_conn;
            server {dns}:80;
        }}
        server {{
            listen 80;
            location / {{
                proxy_pass http://ecs_backend;
                proxy_connect_timeout 5s;
                proxy_read_timeout 10s;
                error_page 502 503 504 /maintenance.html;
            }}
            location /maintenance.html {{
                root /usr/share/nginx/html;
            }}
        }}' | sudo tee /etc/nginx/conf.d/default.conf

        sudo systemctl restart nginx
        """
    )
    return user_data

class EC2WithNginxLBStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, subnet_params: Dict[str,str], sg_id: str, dns: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        self.security_group = ec2.SecurityGroup.from_security_group_id(
                self, "ImportedSG", sg_id, mutable=False
        )
        vpc_id = ssm.StringParameter.value_from_lookup(self, "vpcstack_vpc_vpc_id")
        self.vpc = ec2.Vpc.from_lookup(self, "VPCImported", vpc_id=vpc_id)

        self.nginx_instance = ec2.Instance(
            self,
            "MyInstance",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T2, ec2.InstanceSize.MICRO),
            machine_image=ec2.MachineImage.generic_linux({
                "us-east-1": "ami-04b4f1a9cf54c11d0"
            }),
            vpc=self.vpc,
            security_group=self.security_group,
            associate_public_ip_address=True,
            key_name=self.find_key_pair().key_pair_name,
            user_data=get_user_data(dns),
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            )
            # vpc_subnets=ec2.SubnetSelection(
            #     subnets=[ec2.Subnet.from_subnet_attributes(self, "ImportedSubnet", subnet_id=subnet_params.get('id'), availability_zone=subnet_params.get('az'))]
            # )
        )

        CfnOutput(self, "NginxPublicDNS",
                  value=self.nginx_instance.instance_public_dns_name
        )

    def find_key_pair(self) -> ec2.KeyPair:
        key_pair_name = "test-key-pair"
        try:
            key_pair = ec2.KeyPair.from_key_pair_attributes(
                self, "KeyPair",
                key_pair_name=key_pair_name,
                type=ec2.KeyPairType.RSA
            )
        except Exception as e:
            # Create the key pair if it doesn't exist
            key_pair = ec2.KeyPair(
                self, "KeyPair",
                key_pair_name=key_pair_name,
                type=ec2.KeyPairType.RSA
            )
        return key_pair



