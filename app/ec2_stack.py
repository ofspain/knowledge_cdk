from typing import Tuple

from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    CfnOutput
)
from constructs import Construct

from app.iam_role_stack import IAMRoleStack
from app.vpc_stack import VpcStack

from typing import List, Tuple
import aws_cdk.aws_iam as iam

def get_user_data(meta_data:dict[str,object]) -> ec2.UserData:
    user_data = ec2.UserData.for_linux()

    # Define the first set of commands
    commands = [
        # Create log files for user data execution
        "sudo touch /var/log/user-data.log",
        "sudo touch /var/log/user-data-error.log",
        "echo 'Starting user data execution of defined commands...' | sudo tee -a /var/log/user-data.log",

        # Set non-interactive mode to suppress prompts
        "export DEBIAN_FRONTEND=noninteractive",

        # Update and upgrade system packages quietly
        "echo 'Updating package lists...' | sudo tee -a /var/log/user-data.log",
        "sudo apt-get update -y --quiet >> /var/log/user-data.log 2>> /var/log/user-data-error.log",
        "echo 'Upgrading system packages...' | sudo tee -a /var/log/user-data.log",
        "sudo apt-get upgrade -y --quiet >> /var/log/user-data.log 2>> /var/log/user-data-error.log",

        # Install essential tools and required packages
        "echo 'Installing wget, unzip, and nginx...' | sudo tee -a /var/log/user-data.log",
        "sudo apt-get install -y --quiet wget unzip nginx >> /var/log/user-data.log 2>> /var/log/user-data-error.log || echo 'wget, unzip, or nginx installation failed' | sudo tee -a /var/log/user-data-error.log",

        "echo 'Installing Java 17 and Java 21...' | sudo tee -a /var/log/user-data.log",
        "sudo apt-get install -y --quiet openjdk-17-jdk openjdk-21-jdk >> /var/log/user-data.log 2>> /var/log/user-data-error.log || echo 'Java installation failed' | sudo tee -a /var/log/user-data-error.log",

        # Configure Java alternatives
        "echo 'Configuring Java alternatives...' | sudo tee -a /var/log/user-data.log",
        "sudo update-alternatives --install /usr/bin/java java /usr/lib/jvm/java-17-openjdk-amd64/bin/java 1 >> /var/log/user-data.log 2>> /var/log/user-data-error.log",
        "sudo update-alternatives --install /usr/bin/java java /usr/lib/jvm/java-21-openjdk-amd64/bin/java 2 >> /var/log/user-data.log 2>> /var/log/user-data-error.log",
        #"sudo update-alternatives --set java /usr/lib/jvm/java-21-openjdk-amd64/bin/java >> /var/log/user-data.log 2>> /var/log/user-data-error.log",
        "sudo update-java-alternatives --set java-1.21.0-openjdk-amd64"

        # Install MySQL and PostgreSQL
        "echo 'Installing MySQL and PostgreSQL Client ...' | sudo tee -a /var/log/user-data.log",
        "sudo apt-get install -y --quiet mysql-client postgresql-client >> /var/log/user-data.log 2>> /var/log/user-data-error.log || echo 'MySQL or PostgreSQL installation failed' | sudo tee -a /var/log/user-data-error.log",

        # Enable and start services
        "echo 'Enabling and starting services...' | sudo tee -a /var/log/user-data.log",
        "sudo systemctl enable --now nginx >> /var/log/user-data.log 2>> /var/log/user-data-error.log",

        # Final success message
        "echo 'User data installation execution completed successfully.' | sudo tee -a /var/log/user-data.log"
    ]

    # Get the commands from provision_app_service
    meta_data = dict(meta_data)  # Convert to a mutable dictionary
    meta_data["error_log"] = "/var/log/user-data-error.log"
    app_service_commands = provision_app_service(meta_data)

    # Concatenate the two sets of commands
    all_commands = commands + list(app_service_commands)

    # Add all commands to user data
    user_data.add_commands(*all_commands)

    return user_data


def provision_app_service(meta_data:dict[str,object]) -> Tuple[str, ...]:

    error_log = str(meta_data.get("error_log"))
    rds_endpoint = meta_data.get("rds_endpoint")
    secret_cred_arn = meta_data.get("secret_cred_arn")
    secret_cred_name = meta_data.get("secret_cred_name")
    default_region = meta_data.get("default_region")

    #kwargs = {"rds_endpoint": rds_endpoint, "rds_arn": rds_arn}


    data = (
        "export JAVA_17_HOME=/usr/lib/jvm/java-17-openjdk-amd64 | sudo tee -a /etc/environment",
        "export JAVA_21_HOME=/usr/lib/jvm/java-21-openjdk-amd64 | sudo tee -a /etc/environment",
        "export pwd=/home/ubuntu",
        "export JAR_DIR=$pwd/jars",
        "export MY_SERVICE=/etc/systemd/system/my-application.service",
        "export ENV_FILE=$pwd/app.env",

        #populate environment app variables
        f'echo "RDS_ENDPOINT={rds_endpoint}" | sudo tee -a $ENV_FILE',
        f'echo "SECRET_ARN={secret_cred_arn}" | sudo tee -a $ENV_FILE',
        f'echo "SECRET_NAME={secret_cred_name}" | sudo tee -a $ENV_FILE',
        f'echo "DEFAULT_REGION={default_region}" | sudo tee -a $ENV_FILE',

        "sudo mkdir -p $JAR_DIR",
        f"sudo wget --retry-connrefused --waitretry=5 --timeout=10 --tries=3 -q -O $JAR_DIR/key-generator.jar https://www.dropbox.com/scl/fi/wgn8rlxk8ts1pepsaftxw/key-generator.jar?rlkey=a86n4jbzi49hdi5ajjen615s8&st=etff7aiq&dl=0 || echo '$(date) - Failed to download JAR' | sudo tee -a {error_log}",
        #f"sudo wget -q -O $JAR_DIR/arbiter-api-1.0.jar https://example.com/path/to/arbiter-api-1.0.jar || echo '$(date) - Failed to download JAR' | sudo tee -a {error_log}",
        "echo '[Unit]\nDescription=My Application' | sudo tee -a $MY_SERVICE",
        f'echo "[Service]\nUser=ubuntu\nWorkingDirectory=$pwd\n" | sudo tee -a $MY_SERVICE',
        f'echo "ExecStart=$JAVA_21_HOME/bin/java -jar -Xmx1800m $JAR_DIR/key-generator.jar" | sudo tee -a $MY_SERVICE',
        f'echo "SuccessExitStatus=143\nEnvironmentFile=$ENV_FILE\n" | sudo tee -a $MY_SERVICE',
        "echo 'TimeoutStopSec=10\nRestart=on-failure\nRestartSec=5' | sudo tee -a $MY_SERVICE",
        "echo '[Install]\nWantedBy=multi-user.target' | sudo tee -a $MY_SERVICE",
        "echo 'User data service creation execution completed successfully.' | sudo tee -a /var/log/user-data.log"

    )

    return data


class EC2Stack(Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc_stack: VpcStack, meta_data: dict[str,object], **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.security_group = None
        self.vpc = vpc_stack.vpc


        # Create the EC2 instance
        self.ec2_instance = ec2.Instance(
            self,
            "MyInstance",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
           # machine_image=ec2.MachineImage.latest_amazon_linux2(),  # Dynamic AMI lookup
            machine_image=ec2.MachineImage.generic_linux({
                "us-east-1": "ami-04b4f1a9cf54c11d0"
            }),
            vpc=self.vpc,
            security_group=vpc_stack.ec2_sg,
            associate_public_ip_address=True,
            key_name=self.find_key_pair().key_pair_name,
            user_data=get_user_data(meta_data),
            vpc_subnets=ec2.SubnetSelection(
                subnets=self.vpc.public_subnets  # Pass the Subnet object, not just the ID
            ),
            role=self.create_iam_role()
        )

        # Output the public IP address
        CfnOutput(
            self, "EC2InstancePublicIP",
            value=self.ec2_instance.instance_public_ip  # Corrected property
        )

    # def provision_security_group(self) -> None:
    #     self.security_group = ec2.SecurityGroup(
    #         self, "my_security_group", vpc=self.vpc,
    #         allow_all_outbound=True
    #     )
    #
    #     self.security_group.add_ingress_rule(
    #         ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "allow ssh"
    #     )
    #     self.security_group.add_ingress_rule(
    #         ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "allow http"
    #     )
    #     self.security_group.add_ingress_rule(
    #         ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "allow https"  # Corrected port
    #     )

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

    def create_iam_role(self) -> iam.Role:
        my_role = IAMRoleStack(self, "EC2Role", entity='ec2.amazonaws.com',
                               roles=["AmazonSSMManagedInstanceCore", "SecretsManagerReadWrite"])
        return my_role.ec2_role
