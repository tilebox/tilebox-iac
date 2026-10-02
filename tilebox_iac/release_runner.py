import base64
import re
from collections.abc import Collection, Mapping
from typing import Final

RUNNER_IMAGE: Final = "ghcr.io/tilebox/runner:latest"
_ENVIRONMENT_VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def validate_runner_image(image: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:@-]*", image) is None:
        raise ValueError("runner_image must be a container image reference without whitespace or shell characters")
    return image


def validate_environment_variable_name(name: str) -> None:
    if _ENVIRONMENT_VARIABLE_NAME.fullmatch(name) is None:
        raise ValueError(f"Invalid environment variable name: {name!r}")


def validate_cluster_environment_variables(
    environment: Collection[str], secrets: Collection[str], *, cache_enabled: bool = False
) -> None:
    if "TILEBOX_API_KEY" in environment or "TILEBOX_API_KEY" in secrets:
        raise ValueError("Use tilebox_api_key to set TILEBOX_API_KEY")
    if set(environment) & set(secrets):
        raise ValueError("Environment and secret mappings must not overlap")
    if cache_enabled and ("TILEBOX_WORKER_CACHE" in environment or "TILEBOX_WORKER_CACHE" in secrets):
        raise ValueError("TILEBOX_WORKER_CACHE is set by the cluster's cache")
    for key in (*environment, *secrets):
        validate_environment_variable_name(key)


def encode_environment_variables(environment_variables: Mapping[str, str]) -> str:
    lines = []
    for name, value in sorted(environment_variables.items()):
        validate_environment_variable_name(name)
        if "\r" in value or "\n" in value or "\0" in value:
            raise ValueError(f"Environment variable {name!r} contains an unsupported control character")
        lines.append(f"{name}={value}\n")
    return base64.b64encode("".join(lines).encode()).decode()


__all__ = ["RUNNER_IMAGE"]
