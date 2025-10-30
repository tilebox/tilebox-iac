import json
from pathlib import Path

from dirhash import dirhash
from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_command.local import Command


class LocalBuildTrigger(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        gcp_region: str,
        gcp_project: str,
        repository_id: Input[str],
        source_dir: Path,
        opts: ResourceOptions | None = None,
    ) -> None:
        """A local build trigger that builds a Docker image on code changes and pushes it to a Google Artifact Registry repository.

        Args:
            name: Name of the image.
            gcp_region: Region of the GCP project.
            gcp_project: GCP project ID.
            repository_id: ID of the artifact registry repository.
            source_dir: Path to the source directory.
            opts: Pulumi resource options.
        """
        super().__init__("tilebox:LocalBuildTrigger", name, opts=opts)
        hostname = f"{gcp_region}-docker.pkg.dev"

        # Calculate the hash of the source code to use as an immutable image tag.
        self.tag = dirhash(source_dir, "sha256", match=["*.py", "*.toml", "Dockerfile", "*.md"], ignore=[".venv/*"])

        def build_config(repo_id: str) -> str:
            # https://cloud.google.com/build/docs/build-config-file-schema
            build_config = {
                "options": {
                    "machineType": "E2_HIGHCPU_8",
                    "env": ["DOCKER_BUILDKIT=1"],
                },
                "steps": [
                    {
                        # 1. Pull multiple cache sources in parallel for better cache hit rates
                        "name": "gcr.io/cloud-builders/docker",
                        "entrypoint": "bash",
                        # Pull latest stage for cache (remove base/deps as they're not built as separate targets)
                        "args": [
                            "-c",
                            f"docker pull {hostname}/{gcp_project}/{repo_id}/{name}:latest || true &\nwait",
                        ],
                    },
                    {
                        # 2. Build with BuildKit and multi-stage caching for maximum speed
                        "name": "gcr.io/cloud-builders/docker",
                        "env": ["DOCKER_BUILDKIT=1"],
                        "args": [
                            "build",
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
                        # 3. Push main image and intermediate stages in parallel
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
            # The 'triggers' property ensures this command re-runs when the code changes.
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
