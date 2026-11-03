# The default VPC of the region and its default subnets, one in each zone, as a load balancer needs two zones and
# the function needs no VPC, only with the load balancer
data "aws_vpc" "default" {
  default = true

  lifecycle {
    enabled = var.alb
  }
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }

  filter {
    name   = "default-for-az"
    values = ["true"]
  }

  lifecycle {
    enabled = var.alb
  }
}
