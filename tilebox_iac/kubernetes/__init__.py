import hashlib
import json
import math
import re
from collections.abc import Sequence
from typing import cast

from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_kubernetes import apps, autoscaling, core
from pulumi_kubernetes.core.v1.Secret import Secret
from pulumi_kubernetes.core.v1.ServiceAccount import ServiceAccount

from tilebox_iac.release_runner import RUNNER_IMAGE, encode_environment_variables, validate_runner_image


def _validate_environment(values: dict[str, str]) -> dict[str, str]:
    encode_environment_variables(values)
    if not values.get("TILEBOX_API_KEY"):
        raise ValueError("environment_variables must include a non-empty TILEBOX_API_KEY")
    return values


class Runner(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        environment_variables: dict[str, Input[str]],
        runner_cpu_request: str,
        *,
        runner_memory_request: str | None = None,
        runner_image: Input[str] = RUNNER_IMAGE,
        cpu_target: float = 0.2,
        min_replicas: int = 1,
        max_replicas: int = 10,
        namespace: str | None = None,
        create_namespace: bool = True,
        image_pull_secret_names: Sequence[str] = (),
        opts: ResourceOptions | None = None,
    ) -> None:
        """Run one Tilebox pod per labelled worker with CPU-based horizontal autoscaling."""
        namespace = name if namespace is None else namespace
        for value in (name, namespace):
            if re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", value) is None:
                raise ValueError("name and namespace must be lowercase Kubernetes DNS labels")
        if not 1 <= min_replicas <= max_replicas or not 0 < cpu_target <= 1 or math.floor(cpu_target * 100 + 0.5) < 1:
            raise ValueError("Require 1 <= min_replicas <= max_replicas and a CPU target of 1-100 percent")
        for value in (runner_cpu_request, runner_memory_request):
            if value is None:
                continue
            quantity = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(?:m|[EPTGMK]i?|[eE][+-]?[0-9]+)?", value)
            if quantity is None or float(quantity[1]) <= 0:
                raise ValueError("Resource requests must be positive Kubernetes quantities")
        super().__init__("tilebox:kubernetes:Runner", name, opts=opts)
        ns = (
            core.v1.Namespace(name, metadata={"name": namespace}, opts=ResourceOptions(parent=self))
            if create_namespace
            else None
        )
        child = ResourceOptions(parent=self, depends_on=[ns] if ns else [])
        labels = {"app.kubernetes.io/name": "tilebox-runner", "app.kubernetes.io/instance": name}
        environment = cast(
            Output[dict[str, str]],
            Output.secret(Output.apply(Output.all(**environment_variables), _validate_environment)),
        )
        self.environment = Secret(
            f"{name}-environment",
            metadata={"namespace": namespace},
            string_data=environment,
            type="Opaque",
            opts=child,
        )
        self.service_account = ServiceAccount(
            name,
            metadata={"namespace": namespace},
            automount_service_account_token=False,
            opts=child,
        )
        requests = {"cpu": runner_cpu_request}
        if runner_memory_request is not None:
            requests["memory"] = runner_memory_request
        self.deployment = apps.v1.Deployment(
            name,
            metadata={"namespace": namespace, "labels": labels},
            spec={
                "replicas": min_replicas,
                "selector": {"match_labels": labels},
                "strategy": {"type": "RollingUpdate", "rolling_update": {"max_surge": 0, "max_unavailable": 1}},
                "template": {
                    "metadata": {
                        "labels": labels,
                        "annotations": {
                            "tilebox.com/environment-checksum": Output.apply(
                                environment,
                                lambda values: hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest(),
                            )
                        },
                    },
                    "spec": {
                        "service_account_name": self.service_account.metadata["name"],
                        "automount_service_account_token": False,
                        "termination_grace_period_seconds": 30,
                        "node_selector": {"tilebox.com/runner-pool": name},
                        "image_pull_secrets": [{"name": secret} for secret in image_pull_secret_names],
                        "affinity": {
                            "pod_anti_affinity": {
                                "required_during_scheduling_ignored_during_execution": [
                                    {
                                        "topology_key": "kubernetes.io/hostname",
                                        "label_selector": {"match_labels": labels},
                                    }
                                ]
                            }
                        },
                        "containers": [
                            {
                                "name": "runner",
                                "image": Output.apply(Output.from_input(runner_image), validate_runner_image),
                                "env_from": [{"secret_ref": {"name": self.environment.metadata["name"]}}],
                                "resources": {"requests": requests},
                            }
                        ],
                    },
                },
            },
            opts=ResourceOptions(
                parent=self, depends_on=[self.environment, self.service_account], ignore_changes=["spec.replicas"]
            ),
        )
        self.autoscaler = autoscaling.v2.HorizontalPodAutoscaler(
            name,
            metadata={"namespace": namespace},
            spec={
                "min_replicas": min_replicas,
                "max_replicas": max_replicas,
                "scale_target_ref": {
                    "api_version": "apps/v1",
                    "kind": "Deployment",
                    "name": self.deployment.metadata["name"],
                },
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {
                                "type": "Utilization",
                                "average_utilization": math.floor(cpu_target * 100 + 0.5),
                            },
                        },
                    }
                ],
                "behavior": {
                    "scale_down": {
                        "stabilization_window_seconds": 300,
                        "policies": [
                            {
                                "type": "Percent",
                                "value": 100,
                                "period_seconds": 15,
                            }
                        ],
                    }
                },
            },
            opts=child,
        )
        self.register_outputs({"deployment_name": self.deployment.metadata["name"], "namespace": namespace})
