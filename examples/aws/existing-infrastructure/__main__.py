import pulumi

from tilebox_iac.aws.runner import AutoScalingCluster

config = pulumi.Config()
role_name = config.get("roleName")
profile_name = config.get("instanceProfileName")
if (role_name is None) != (profile_name is None):
    raise ValueError("Set roleName and instanceProfileName together")
cluster = AutoScalingCluster(
    "runners",
    instance_type="m7i.large",
    cpu_target=0.2,
    cluster_enabled=True,
    min_replicas_config=1,
    max_replicas_config=10,
    subnet_ids=config.require_object("subnetIds"),
    security_group_ids=config.require_object("securityGroupIds"),
    secret_environment_variables={
        "TILEBOX_API_KEY": {
            "secret_arn": config.require("apiKeySecretArn"),
            "rollout_marker": config.get("secretRevision") or "1",
        },
    },
    iam_config={"existing_role_name": role_name, "existing_instance_profile_name": profile_name}
    if role_name is not None and profile_name is not None
    else None,
)
pulumi.export("autoscalingGroupName", cluster.asg.name if cluster.asg is not None else None)
