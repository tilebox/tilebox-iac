import pulumi

from tilebox_iac import creodias

config = pulumi.Config()
provider = creodias.Provider("cloudferro", region=config.require("region"), token=config.require_secret("token"))
cluster = creodias.Cluster(
    "runners",
    kubernetes_version=config.require("kubernetesVersion"),
    control_plane_flavor="eo1a.medium",
    control_plane_size=1,
    worker_flavor="eo2a.large",
    opts=pulumi.ResourceOptions(provider=provider),
)
pulumi.export("kubeconfig", cluster.kubeconfig)
