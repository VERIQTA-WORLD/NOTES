terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}
provider "aws" { region = var.region }
variable "region" {
  type = string
  default = "us-east-1"
}
variable "ami_id" {
  type = string
  description = "Reviewed x86_64 Linux AMI available in the selected Region"
  validation {
    condition = can(regex("^ami-[0-9a-f]+$", var.ami_id))
    error_message = "Supply a real AMI ID for this Region."
  }
}
variable "instance_type" {
  type = string
  default = "t3.micro"
}
variable "revision" {
  type = string
  default = "v1"
  validation {
    condition = can(regex("^[A-Za-z0-9._-]{1,40}$", var.revision))
    error_message = "Use a short release identifier."
  }
}
resource "aws_vpc" "lab" {
  cidr_block = "10.68.0.0/16"
  tags = { Name = "veriqta-plan-lab" }
}
resource "aws_subnet" "lab" {
  vpc_id = aws_vpc.lab.id
  cidr_block = "10.68.1.0/24"
  map_public_ip_on_launch = false
}
resource "aws_security_group" "lab" {
  name_prefix = "veriqta-plan-"
  description = "Isolated plan exercise; no inbound rules"
  vpc_id = aws_vpc.lab.id
}
resource "aws_instance" "veriqta" {
  ami = var.ami_id
  instance_type = var.instance_type
  subnet_id = aws_subnet.lab.id
  vpc_security_group_ids = [aws_security_group.lab.id]
  associate_public_ip_address = false
  user_data = <<-SCRIPT
    #!/bin/sh
    echo '${var.revision}' > /var/lib/veriqta-release
  SCRIPT
  user_data_replace_on_change = true
  metadata_options {
    http_tokens = "required"
    http_endpoint = "enabled"
  }
  root_block_device {
    encrypted = true
    volume_size = 8
    volume_type = "gp3"
  }
  tags = { Name = "veriqta-plan-lab", Environment = "training" }
}
