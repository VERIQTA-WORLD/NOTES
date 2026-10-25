terraform {
  required_version = ">= 1.5, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
variable "region" {
  type    = string
  default = "us-east-1"
}
provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "devops-notes-lab" }
  }
}
data "aws_availability_zones" "available" {
  state = "available"
}
resource "aws_vpc" "lab" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
}
resource "aws_subnet" "private" {
  count                   = 2
  vpc_id                  = aws_vpc.lab.id
  cidr_block              = cidrsubnet(aws_vpc.lab.cidr_block, 8, count.index + 1)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false
}
output "vpc_id" {
  value = aws_vpc.lab.id
}
output "subnet_ids" {
  value = aws_subnet.private[*].id
}
