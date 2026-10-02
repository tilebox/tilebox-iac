import pulumi

from tilebox_iac import gcp

cluster = gcp.Cluster(
    "runners",
    project=pulumi.Config("gcp").require("project"),
    tilebox_api_key=pulumi.Config().require_secret("tileboxApiKey"),
)
pulumi.export("instanceGroup", cluster.runner.mig.instance_group if cluster.runner.mig is not None else None)
