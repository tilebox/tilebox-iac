import ipaddress

from pulumi import ComponentResource, ResourceOptions
from pulumi_azure_native import network


class Network(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        resource_group_name: str,
        location: str,
        enable_internet_access: bool = True,
        cidr_block: str = "10.10.0.0/16",
        opts: ResourceOptions | None = None,
    ) -> None:
        """An Azure VNet with a private subnet and optional NAT Gateway for outbound internet access."""
        super().__init__("tilebox:azure:Network", name, opts=opts)

        vnet_network = ipaddress.ip_network(cidr_block)
        if vnet_network.prefixlen > 24:
            msg = f"CIDR block {cidr_block} is too small. Must be /24 or larger to accommodate a subnet."
            raise ValueError(msg)
        subnet_cidr = str(next(vnet_network.subnets(new_prefix=24)))

        self.virtual_network = network.VirtualNetwork(
            f"{name}-vnet",
            resource_group_name=resource_group_name,
            virtual_network_name=f"{name}-vnet",
            location=location,
            address_space={"address_prefixes": [cidr_block]},
            opts=ResourceOptions(parent=self),
        )

        nat_gateway_id = None
        if enable_internet_access:
            public_ip = network.PublicIPAddress(
                f"{name}-nat-ip",
                resource_group_name=resource_group_name,
                public_ip_address_name=f"{name}-nat-ip",
                location=location,
                public_ip_allocation_method="Static",
                sku={"name": "Standard"},
                opts=ResourceOptions(depends_on=[self.virtual_network], parent=self),
            )
            nat_gateway = network.NatGateway(
                f"{name}-nat",
                resource_group_name=resource_group_name,
                nat_gateway_name=f"{name}-nat",
                location=location,
                sku={"name": "Standard"},
                public_ip_addresses=[{"id": public_ip.id}],
                opts=ResourceOptions(depends_on=[public_ip], parent=self),
            )
            nat_gateway_id = nat_gateway.id

        self.subnet = network.Subnet(
            f"{name}-subnet",
            resource_group_name=resource_group_name,
            virtual_network_name=self.virtual_network.name,
            subnet_name=f"{name}-subnet",
            address_prefix=subnet_cidr,
            nat_gateway={"id": nat_gateway_id} if nat_gateway_id is not None else None,
            opts=ResourceOptions(depends_on=[self.virtual_network], parent=self),
        )

        self.id = self.virtual_network.id
        self.subnet_id = self.subnet.id
        self.register_outputs({"id": self.id, "subnet_id": self.subnet_id})
