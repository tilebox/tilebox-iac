from pulumi import Alias, ComponentResource, Input, ResourceOptions
from pulumi_gcp.compute import Network as _Network
from pulumi_gcp.compute import Router, RouterNat, Subnetwork


class Network(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        gcp_region: str,
        enable_private_google_access: bool = True,
        enable_internet_access: bool = True,
        opts: ResourceOptions | None = None,
        *,
        gcp_project: Input[str] | None = None,
    ) -> None:
        """Create a private subnet with optional Google API access and outbound NAT."""
        opts = ResourceOptions.merge(opts, ResourceOptions(aliases=[Alias(type_="tilebox:GCPNetwork")]))
        super().__init__("tilebox:gcp:Network", name, opts=opts)

        self.network = _Network(
            f"{name}-network",
            project=gcp_project,
            name=f"{name}-network",
            auto_create_subnetworks=False,
            opts=ResourceOptions(parent=self),
        )
        self.subnet = Subnetwork(
            f"{name}-subnet",
            project=gcp_project,
            name=f"{name}-subnet",
            ip_cidr_range="10.10.0.0/24",
            network=self.network.self_link,
            region=gcp_region,
            private_ip_google_access=enable_private_google_access,
            opts=ResourceOptions(depends_on=[self.network], parent=self),
        )

        if enable_internet_access:
            self.router = Router(
                f"{name}-router",
                project=gcp_project,
                name=f"{name}-router",
                network=self.network.self_link,
                region=gcp_region,
                opts=ResourceOptions(depends_on=[self.network], parent=self),
            )
            self.router_nat = RouterNat(
                f"{name}-nat",
                project=gcp_project,
                name=f"{name}-nat",
                router=self.router.name,
                region=gcp_region,
                source_subnetwork_ip_ranges_to_nat="LIST_OF_SUBNETWORKS",
                subnetworks=[
                    {
                        "name": self.subnet.id,
                        "source_ip_ranges_to_nats": ["ALL_IP_RANGES"],
                    }
                ],
                nat_ip_allocate_option="AUTO_ONLY",
                opts=ResourceOptions(depends_on=[self.router], parent=self),
            )

        self.id = self.network.id
        self.subnet_id = self.subnet.id
        self.register_outputs({"id": self.id, "subnet_id": self.subnet_id})
