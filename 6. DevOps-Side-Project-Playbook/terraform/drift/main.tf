terraform {
  required_version = ">= 1.10, < 2.0"
  backend "s3" {}
  required_providers { aws = { source = "hashicorp/aws", version = "~> 6.0" } }
}
provider "aws" { region = var.region }
variable "region" { type = string }
resource "aws_vpc" "lab" {
  cidr_block = "10.42.0.0/16"
  tags = { Name = "veriqta-drift-lab", Owner = "veriqta" }
}
resource "aws_security_group" "lab" {
  name_prefix = "veriqta-drift-"
  description = "Unattached drift exercise security group"
  vpc_id = aws_vpc.lab.id
  tags = { Name = "veriqta-drift-lab" }
}
resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.lab.id
  ip_protocol = "tcp"
  from_port = 22
  to_port = 22
  cidr_ipv4 = "10.42.0.0/16"
}
output "security_group_id" { value = aws_security_group.lab.id }
output "ingress_rule_id" { value = aws_vpc_security_group_ingress_rule.ssh.id }
