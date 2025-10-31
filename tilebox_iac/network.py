from pulumi import ComponentResource, ResourceOptions
from pulumi_gcp.compute import Network, Router, RouterNat, Subnetwork


class GCPNetwork(ComponentResource):
    def __init__(
        self,
        name: str,
        gcp_region: str,
        enable_private_google_access: bool = True,
        enable_internet_access: bool = True,
        opts: ResourceOptions | None = None,
    ) -> None:
        """A network with optional Private Google Access (PGA) and an optional router for outbound internet access.

        If
        Private Google Access (PGA) allows VMs to access Google APIs and services using an internal IP address.
        That way, Cloud services or GCS buckets can be accessed without incurring egress charges.

        If `enable_internet_access` is set to `True`, a router and RouterNAT are created to allow VMs to
        access the internet (outbound).

        Args:
            name: Name of the network.
            gcp_region: The GCP region to deploy the network in.
            opts: Pulumi resource options.
        """
        super().__init__("tilebox:GCPNetwork", name, opts=opts)

        self.network = Network(
            f"{name}-network",
            name=f"{name}-network",
            auto_create_subnetworks=False,
            opts=ResourceOptions(parent=self),
        )
        self.subnet = Subnetwork(
            f"{name}-subnet",
            name=f"{name}-subnet",
            ip_cidr_range="10.10.0.0/24",
            network=self.network.self_link,
            region=gcp_region,
            private_ip_google_access=enable_private_google_access,
            opts=ResourceOptions(depends_on=[self.network], parent=self),
        )

        if enable_internet_access:
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
