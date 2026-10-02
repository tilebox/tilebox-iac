from pathlib import Path

import pulumi
import pulumi_kubernetes

from tilebox_iac import kubernetes

config = pulumi.Config()
provider = pulumi_kubernetes.Provider(
    "cluster",
    kubeconfig=pulumi.Output.secret(Path(config.require("kubeconfigPath")).expanduser().read_text()),
)
runner = kubernetes.Runner(
    "runners",
    environment_variables={"TILEBOX_API_KEY": config.require_secret("tileboxApiKey")},
    runner_cpu_request="1000m",
    opts=pulumi.ResourceOptions(provider=provider),
)
pulumi.export("deploymentName", runner.deployment.metadata["name"])
