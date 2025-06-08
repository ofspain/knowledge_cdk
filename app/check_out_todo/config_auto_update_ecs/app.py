#!/usr/bin/env python3
import aws_cdk as cdk
from cdk_stack import ConfigUpdateStack

app = cdk.App()
ConfigUpdateStack(app, "ConfigUpdateStack")
app.synth()
