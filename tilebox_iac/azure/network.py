from pulumi import ComponentResource, Input, Output, ResourceOptions
from pulumi_azure import network

from tilebox_iac.azure._naming import resource_name


class Network(ComponentResource):
    def __init__(
        self,
        name: str,
        resource_group_name: Input[str],
        location: Input[str],
        opts: ResourceOptions | None = None,
    ) -> None:
        """Create a runner subnet with outbound NAT and no inbound access."""
        super().__init__("tilebox:azure:Network", name, opts=opts)
        child = ResourceOptions(parent=self)
        vnet = network.VirtualNetwork(
            resource_name(name, 56),
            resource_group_name=resource_group_name,
            location=location,
            address_spaces=["10.10.0.0/16"],
            opts=child,
        )
        security = network.NetworkSecurityGroup(
            resource_name(name, 72),
            resource_group_name=resource_group_name,
            location=location,
            security_rules=[
                {
                    "name": "deny-inbound",
                    "priority": 100,
                    "direction": "Inbound",
                    "access": "Deny",
                    "protocol": "*",
                    "source_port_range": "*",
                    "destination_port_range": "*",
                    "source_address_prefix": "*",
                    "destination_address_prefix": "*",
                }
            ],
            opts=child,
        )
        subnet = network.Subnet(
            resource_name(name, 72),
            resource_group_name=resource_group_name,
            virtual_network_name=vnet.name,
            address_prefixes=["10.10.1.0/24"],
            opts=child,
        )
        public_ip = network.PublicIp(
            resource_name(name, 72),
            resource_group_name=resource_group_name,
            location=location,
            allocation_method="Static",
            sku="Standard",
            opts=child,
        )
        nat = network.NatGateway(
            resource_name(name, 17), resource_group_name=resource_group_name, location=location, opts=child
        )
        egress = network.NatGatewayPublicIpAssociation(
            name, nat_gateway_id=nat.id, public_ip_address_id=public_ip.id, opts=child
        )
        association = network.SubnetNatGatewayAssociation(
            name,
            subnet_id=subnet.id,
            nat_gateway_id=nat.id,
            opts=ResourceOptions(parent=self, depends_on=[egress]),
        )
        firewall = network.SubnetNetworkSecurityGroupAssociation(
            name, subnet_id=subnet.id, network_security_group_id=security.id, opts=child
        )
        # Wait for NAT and firewall setup before returning the subnet ID.
        self.subnet_id: Output[str] = Output.apply(
            Output.all(nat=association.subnet_id, firewall=firewall.subnet_id),
            lambda subnet_ids: subnet_ids["firewall"],
        )
        self.register_outputs({"subnet_id": self.subnet_id})
