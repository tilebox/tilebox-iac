import json
from pathlib import Path

from dirhash import dirhash
from pulumi import Alias, ComponentResource, Input, Output, ResourceOptions
from pulumi_command.local import Command


class LocalBuildTrigger(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        gcp_region: str,
        gcp_project: str,
        repository_id: Input[str],
        source_dir: Path,
        additional_ignore_patterns: list[str] | None = None,
        platform: str = "linux/amd64",
        opts: ResourceOptions | None = None,
    ) -> None:
        """A local build trigger that builds a Docker image on code changes and pushes it to a Google Artifact Registry repository.

        Args:
            name: Name of the image.
            gcp_region: Region of the GCP project.
            gcp_project: GCP project ID.
            repository_id: ID of the artifact registry repository.
            source_dir: Path to the source directory.
            additional_ignore_patterns: Additional ignore patterns for excluding files or directories when determining
                if the source code has changed, and therefore if the image needs to be rebuilt.
            platform: Docker platform to build for (e.g., "linux/amd64" or "linux/arm64").
            opts: Pulumi resource options.
        """
        opts = ResourceOptions.merge(opts, ResourceOptions(aliases=[Alias(type_="tilebox:LocalBuildTrigger")]))
        super().__init__("tilebox:gcp:LocalBuildTrigger", name, opts=opts)
        hostname = f"{gcp_region}-docker.pkg.dev"

        ignore = [".venv/*"] + (additional_ignore_patterns or [])
        # Include all files so extensionless runtime binaries (for example `dynamic_runner/tilebox`)
        # trigger rebuilds reliably.
        self.tag = dirhash(source_dir, "sha256", match=["*", "**/*"], ignore=ignore)

        def build_config(repo_id: str) -> str:
            build_config = {
                "options": {
                    "machineType": "E2_HIGHCPU_8",
                    "env": ["DOCKER_BUILDKIT=1"],
                },
                "steps": [
                    {
                        "name": "gcr.io/cloud-builders/docker",
                        "entrypoint": "bash",
                        "args": [
                            "-c",
                            f"docker pull {hostname}/{gcp_project}/{repo_id}/{name}:latest || true &\nwait",
                        ],
                    },
                    {
                        "name": "gcr.io/cloud-builders/docker",
                        "env": ["DOCKER_BUILDKIT=1"],
                        "args": [
                            "build",
                            "--platform",
                            platform,
                            "-t",
                            f"{hostname}/{gcp_project}/{repo_id}/{name}:{self.tag}",
                            "--cache-from",
                            f"{hostname}/{gcp_project}/{repo_id}/{name}:latest",
                            "--build-arg",
                            "BUILDKIT_INLINE_CACHE=1",
                            ".",
                        ],
                    },
                    {
                        "name": "gcr.io/cloud-builders/docker",
                        "entrypoint": "bash",
                        "args": [
                            "-c",
                            f"docker push {hostname}/{gcp_project}/{repo_id}/{name}:{self.tag} &\n"
                            f"docker tag {hostname}/{gcp_project}/{repo_id}/{name}:{self.tag} {hostname}/{gcp_project}/{repo_id}/{name}:latest\n"
                            f"docker push {hostname}/{gcp_project}/{repo_id}/{name}:latest &\n"
                            "wait",
                        ],
                    },
                ],
                "images": [
                    f"{hostname}/{gcp_project}/{repo_id}/{name}:{self.tag}",
                    f"{hostname}/{gcp_project}/{repo_id}/{name}:latest",
                ],
                "timeout": "600s",
            }
            return json.dumps(build_config)

        self.cloud_build = Command(
            f"{name}-cloud-build-image",
            create=f"gcloud builds submit --config=/dev/stdin --project={gcp_project} {source_dir}",
            stdin=Output.from_input(repository_id).apply(build_config),
            triggers=[self.tag],
            opts=ResourceOptions(parent=self),
        )

        self.container_image = Output.concat(hostname, "/", gcp_project, "/", repository_id, "/", name)

        self.register_outputs(
            {
                "container_image": self.container_image,
                "code_hash": self.tag,
            }
        )
