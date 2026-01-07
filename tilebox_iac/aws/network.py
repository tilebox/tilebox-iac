import pulumi_aws.ec2 as aws_ec2
from pulumi import ComponentResource, ResourceOptions


class AWSNetwork(ComponentResource):
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        aws_region: str,
        enable_s3_endpoint: bool = True,
        enable_internet_access: bool = True,
        cidr_block: str = "10.10.0.0/16",
        opts: ResourceOptions | None = None,
    ) -> None:
        """An AWS VPC network with public and private subnets, optional NAT Gateway and S3 VPC endpoint.

        Args:
            name: Name of the network.
            aws_region: The AWS region to deploy the network in.
            enable_s3_endpoint: Whether to create an S3 Gateway VPC endpoint for private subnet access to S3
                without incurring NAT Gateway data transfer charges.
            enable_internet_access: Whether to enable internet access for VMs in the private subnet. If `True`,
                an Elastic IP and NAT Gateway are created to allow instances to access the internet (outbound).
            cidr_block: The CIDR block for the VPC.
            opts: Pulumi resource options.
        """
        super().__init__("tilebox:aws:Network", name, opts=opts)

        self.vpc = aws_ec2.Vpc(
            f"{name}-vpc",
            cidr_block=cidr_block,
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags={"Name": f"{name}-vpc"},
            opts=ResourceOptions(parent=self),
        )
        self.vpc_id = self.vpc.id

        first_az = f"{aws_region}a"

        self.public_subnet = aws_ec2.Subnet(
            f"{name}-public-subnet",
            vpc_id=self.vpc.id,
            cidr_block="10.10.1.0/24",
            availability_zone=first_az,
            map_public_ip_on_launch=True,
            tags={"Name": f"{name}-public-subnet"},
            opts=ResourceOptions(depends_on=[self.vpc], parent=self),
        )
        self.public_subnet_id = self.public_subnet.id

        self.private_subnet = aws_ec2.Subnet(
            f"{name}-private-subnet",
            vpc_id=self.vpc.id,
            cidr_block="10.10.2.0/24",
            availability_zone=first_az,
            tags={"Name": f"{name}-private-subnet"},
            opts=ResourceOptions(depends_on=[self.vpc], parent=self),
        )
        self.private_subnet_id = self.private_subnet.id

        internet_gateway = aws_ec2.InternetGateway(
            f"{name}-igw",
            vpc_id=self.vpc.id,
            tags={"Name": f"{name}-igw"},
            opts=ResourceOptions(depends_on=[self.vpc], parent=self),
        )

        public_route_table = aws_ec2.RouteTable(
            f"{name}-public-rt",
            vpc_id=self.vpc.id,
            routes=[
                {
                    "cidr_block": "0.0.0.0/0",
                    "gateway_id": internet_gateway.id,
                }
            ],
            tags={"Name": f"{name}-public-rt"},
            opts=ResourceOptions(depends_on=[internet_gateway], parent=self),
        )

        aws_ec2.RouteTableAssociation(
            f"{name}-public-rta",
            subnet_id=self.public_subnet.id,
            route_table_id=public_route_table.id,
            opts=ResourceOptions(depends_on=[public_route_table, self.public_subnet], parent=self),
        )

        self.private_route_table: aws_ec2.RouteTable | None = None

        if enable_internet_access:
            eip = aws_ec2.Eip(
                f"{name}-nat-eip",
                domain="vpc",
                tags={"Name": f"{name}-nat-eip"},
                opts=ResourceOptions(parent=self),
            )

            nat_gateway = aws_ec2.NatGateway(
                f"{name}-nat",
                allocation_id=eip.id,
                subnet_id=self.public_subnet.id,
                tags={"Name": f"{name}-nat"},
                opts=ResourceOptions(depends_on=[eip, self.public_subnet, internet_gateway], parent=self),
            )

            self.private_route_table = aws_ec2.RouteTable(
                f"{name}-private-rt",
                vpc_id=self.vpc.id,
                routes=[
                    {
                        "cidr_block": "0.0.0.0/0",
                        "nat_gateway_id": nat_gateway.id,
                    }
                ],
                tags={"Name": f"{name}-private-rt"},
                opts=ResourceOptions(depends_on=[nat_gateway], parent=self),
            )

            aws_ec2.RouteTableAssociation(
                f"{name}-private-rta",
                subnet_id=self.private_subnet.id,
                route_table_id=self.private_route_table.id,
                opts=ResourceOptions(depends_on=[self.private_route_table, self.private_subnet], parent=self),
            )

        if enable_s3_endpoint and self.private_route_table is not None:
            aws_ec2.VpcEndpoint(
                f"{name}-s3-endpoint",
                vpc_id=self.vpc.id,
                service_name=f"com.amazonaws.{aws_region}.s3",
                vpc_endpoint_type="Gateway",
                route_table_ids=[self.private_route_table.id],
                tags={"Name": f"{name}-s3-endpoint"},
                opts=ResourceOptions(depends_on=[self.private_route_table], parent=self),
            )

        self.register_outputs(
            {
                "vpc_id": self.vpc_id,
                "public_subnet_id": self.public_subnet_id,
                "private_subnet_id": self.private_subnet_id,
            }
        )
