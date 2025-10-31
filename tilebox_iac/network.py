from pulumi import ComponentResource, ResourceOptions
from pulumi_gcp.compute import Network, Router, RouterNat, Subnetwork


class TileboxNetwork(ComponentResource):
    def __init__(
        self,
        name: str,
        gcp_region: str,
        opts: ResourceOptions | None = None,
    ) -> None:
        """A network with Private Google Access (PGA) enabled and a router for outbound internet access.

        Args:
            name: Name of the network.
            gcp_region: The GCP region to deploy the network in.
            opts: Pulumi resource options.
        """
        super().__init__("tilebox:TileboxNetwork", name, opts=opts)

        self.network = Network(
            f"{name}-network",
            name=f"{name}-network",
            auto_create_subnetworks=False,
            opts=ResourceOptions(parent=self),
        )
        self.pga_subnet = Subnetwork(
            f"{name}-pga-subnet",
            name=f"{name}-pga-subnet",
            ip_cidr_range="10.10.0.0/24",
            network=self.network.self_link,
            region=gcp_region,
            private_ip_google_access=True,  # Private Google Access (PGA) enabled
            opts=ResourceOptions(depends_on=[self.network], parent=self),
        )

        # Router and RouterNAT allow VMs to access the internet (outbound)
        self.router = Router(
            f"{name}-router",
            name=f"{name}-router",
            network=self.network.self_link,
            region=gcp_region,
            opts=ResourceOptions(depends_on=[self.network], parent=self),
        )
        self.router_nat = RouterNat(
            f"{name}-nat",
            name=f"{name}-nat",
            router=self.router.name,
            region=gcp_region,
            source_subnetwork_ip_ranges_to_nat="ALL_SUBNETWORKS_ALL_IP_RANGES",
            nat_ip_allocate_option="AUTO_ONLY",
            opts=ResourceOptions(depends_on=[self.router], parent=self),
        )

        self.register_outputs({})
