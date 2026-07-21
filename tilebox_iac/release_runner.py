import base64
import re
from collections.abc import Mapping
from typing import Final

RUNNER_IMAGE: Final = "ghcr.io/tilebox/runner:latest"
_ENVIRONMENT_VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def validate_environment_variable_name(name: str) -> None:
    if _ENVIRONMENT_VARIABLE_NAME.fullmatch(name) is None:
        raise ValueError(f"Invalid environment variable name: {name!r}")


def encode_environment_variables(environment_variables: Mapping[str, str]) -> str:
    lines = []
    for name, value in sorted(environment_variables.items()):
        validate_environment_variable_name(name)
        if "\r" in value or "\n" in value or "\0" in value:
            raise ValueError(f"Environment variable {name!r} contains an unsupported control character")
        lines.append(f"{name}={value}\n")
    return base64.b64encode("".join(lines).encode()).decode()


__all__ = ["RUNNER_IMAGE"]
