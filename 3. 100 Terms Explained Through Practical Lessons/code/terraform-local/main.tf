terraform {
  required_version = ">= 1.5, < 2.0"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}
provider "docker" {}
resource "docker_image" "web" {
  name         = "nginx:1.28-alpine"
  keep_locally = true
}
resource "docker_container" "web" {
  name  = "devops-terraform-web"
  image = docker_image.web.image_id
  ports {
    internal = 80
    external = 8081
    ip       = "127.0.0.1"
  }
}
output "url" {
  value = "http://127.0.0.1:8081"
}
