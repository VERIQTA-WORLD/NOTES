terraform {
  required_version = ">= 1.10, < 2.0"
}
variable "release" {
  type = string
  default = "v1"
}
resource "terraform_data" "veriqta" {
  input = "Veriqta local replacement exercise"
  triggers_replace = [var.release]
}
output "release" { value = var.release }
