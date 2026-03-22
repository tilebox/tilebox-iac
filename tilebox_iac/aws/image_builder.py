from pathlib import Path

from dirhash import dirhash
from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_command.local import Command


class LocalBuildTrigger(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        aws_region: str,
        aws_account_id: Input[str],
        repository_name: Input[str],
        source_dir: Path,
        additional_ignore_patterns: list[str] | None = None,
        platform: str = "linux/amd64",
        opts: ResourceOptions | None = None,
    ) -> None:
        """A local build trigger that builds a Docker image on code changes and pushes it to an AWS ECR repository.

        Args:
            name: Name of the image.
            aws_region: AWS region.
            aws_account_id: AWS account ID.
            repository_name: ECR repository name.
            source_dir: Path to the source directory.
            additional_ignore_patterns: Additional ignore patterns for excluding files or directories when determining
                if the source code has changed, and therefore if the image needs to be rebuilt.
            platform: Docker platform to build for (e.g., "linux/amd64" or "linux/arm64").
            opts: Pulumi resource options.
        """
        super().__init__("tilebox:aws:ImageBuilder", name, opts=opts)

        # Hash source files to detect changes; tag is used as image tag and Pulumi trigger
        ignore = [".venv/*"] + (additional_ignore_patterns or [])
        # Include all files so extensionless runtime binaries (for example `dynamic_runner/tilebox`)
        # trigger rebuilds reliably.
        self.tag = dirhash(
            source_dir,
            "sha256",
            match=["*", "**/*"],
            ignore=ignore,
        )

        def build_command(args: list[str]) -> str:
            account_id, repo_name = args[0], args[1]
            hostname = f"{account_id}.dkr.ecr.{aws_region}.amazonaws.com"
            image_uri = f"{hostname}/{repo_name}"

            return (
                f"aws ecr get-login-password --region {aws_region} | docker login --username AWS --password-stdin {hostname} && "
                f"docker build --platform {platform} --load -t {image_uri}:{self.tag} {source_dir} && "
                f"docker tag {image_uri}:{self.tag} {image_uri}:latest && "
                f"docker push {image_uri}:{self.tag} && "
                f"docker push {image_uri}:latest"
            )

        self.docker_build = Command(
            f"{name}-docker-build-image",
            create=Output.all(aws_account_id, repository_name).apply(build_command),
            # Only rebuild when source hash changes (content-addressable builds)
            triggers=[self.tag],
            opts=ResourceOptions(parent=self),
        )

        self.container_image = Output.concat(
            aws_account_id, ".dkr.ecr.", aws_region, ".amazonaws.com/", repository_name
        )

        self.register_outputs(
            {
                "container_image": self.container_image,
                "code_hash": self.tag,
            }
        )
