import base64
import json
import re
from collections.abc import Sequence
from typing import cast

import pulumi
from pulumi.runtime import register_package


async def _package() -> str:
    # Use CloudFerro's provider through Pulumi's Terraform provider bridge.
    return await register_package(
        base_provider_name="terraform-provider",
        base_provider_version="1.4.0",
        base_provider_download_url="",
        package_name="cloudferro",
        package_version="0.1.3",
        base64_parameter=base64.b64encode(
            json.dumps(
                {
                    "remote": {"url": "registry.terraform.io/cloudferro/cloudferro", "version": "0.1.3"},
                }
            ).encode()
        ).decode(),
    )


class Provider(pulumi.ProviderResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        *,
        region: pulumi.Input[str] | None = None,
        host: pulumi.Input[str] | None = None,
        token: pulumi.Input[str] | None = None,
        server_cert: pulumi.Input[str] | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        """Configure access to CloudFerro Managed Kubernetes."""
        if region is not None and host is not None:
            raise ValueError("Specify region or host, not both")
        super().__init__(
            "cloudferro",
            name,
            {
                "region": region,
                "host": host,
                "serverCert": server_cert,
                "token": pulumi.Output.secret(token) if token is not None else None,
            },
            pulumi.ResourceOptions.merge(
                opts, pulumi.ResourceOptions(version="0.1.3", additional_secret_outputs=["token"])
            ),
            package_ref=_package(),
        )


class Cluster(pulumi.ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        kubernetes_version: str,
        control_plane_flavor: str,
        worker_flavor: str,
        *,
        control_plane_size: int = 3,
        min_replicas: int = 1,
        max_replicas: int = 10,
        shared_network_ids: Sequence[str] = (),
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        """Create a CREODIAS Kubernetes cluster and an autoscaled, labelled worker pool."""
        if re.fullmatch(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?", name) is None:
            raise ValueError("name must be a lowercase DNS label starting with a letter")
        if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", kubernetes_version) is None:
            raise ValueError("kubernetes_version must be an exact three-part version")
        if control_plane_size not in (1, 3, 5) or not 1 <= min_replicas <= max_replicas:
            raise ValueError("Require 1, 3 or 5 control-plane nodes and 1 <= min_replicas <= max_replicas")
        if not all(value.strip() for value in (control_plane_flavor, worker_flavor, *shared_network_ids)):
            raise ValueError("Flavors and shared network IDs must not be empty")
        super().__init__("tilebox:creodias:Cluster", name, opts=opts)
        self.cluster = pulumi.CustomResource(
            "cloudferro:index/kubernetesClusterV1:KubernetesClusterV1",
            name,
            {
                "name": name,
                "version": kubernetes_version,
                "controlPlane": {
                    "flavor": control_plane_flavor,
                    "size": control_plane_size,
                },
                "kubeconfig": None,
                "routerIp": None,
                "metadata": None,
            },
            pulumi.ResourceOptions(parent=self, version="0.1.3", additional_secret_outputs=["kubeconfig"]),
            package_ref=_package(),
        )
        self.node_pool = pulumi.CustomResource(
            "cloudferro:index/kubernetesNodePoolV1:KubernetesNodePoolV1",
            name,
            {
                "name": name,
                "clusterId": self.cluster.id,
                "flavor": worker_flavor,
                "autoscale": True,
                "sizeMin": min_replicas,
                "sizeMax": max_replicas,
                "labels": [{"key": "tilebox.com/runner-pool", "value": name}],
                "sharedNetworks": list(shared_network_ids),
            },
            pulumi.ResourceOptions(parent=self, version="0.1.3"),
            package_ref=_package(),
        )
        self.kubeconfig = pulumi.Output.secret(cast(pulumi.Output[str], pulumi.get(self.cluster, "kubeconfig")))
        self.register_outputs(
            {"cluster_id": self.cluster.id, "node_pool_id": self.node_pool.id, "kubeconfig": self.kubeconfig}
        )
