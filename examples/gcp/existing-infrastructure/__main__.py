import pulumi

from tilebox_iac.gcp.runner import AutoScalingCluster

config = pulumi.Config()
email = config.get("serviceAccountEmail")
cluster = AutoScalingCluster(
    "runners",
    gcp_project=pulumi.Config("gcp").require("project"),
    gcp_region="europe-west1",
    machine_type="n2-standard-2",
    cpu_target=0.2,
    cluster_enabled=True,
    min_replicas_config=1,
    max_replicas_config=10,
    network_interfaces=[{"network": config.require("networkId"), "subnetwork": config.require("subnetId")}],
    health_check_network_project=config.get("hostProject"),
    roles={"existing_email": email} if email is not None else None,
    secret_environment_variables={
        "TILEBOX_API_KEY": {
            "secret_id": config.require("apiKeySecretId"),
            "rollout_marker": config.get("secretRevision") or "1",
        },
    },
    auto_healing_enabled=config.get_bool("autoHealingEnabled") or False,
)
pulumi.export("instanceGroup", cluster.mig.instance_group if cluster.mig is not None else None)
