import pulumi

from tilebox_iac import aws

cluster = aws.Cluster("runners", pulumi.Config().require_secret("tileboxApiKey"))
pulumi.export("autoscalingGroupName", cluster.runner.asg.name if cluster.runner.asg is not None else None)
