terraform {
  required_version = "~> 1.13.0"

  # The provider is not locked, so that it is the newest of its versions
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.0"
    }
  }
}

# The credentials and the region of the default chain of AWS: the variables of the environment, the profile and the
# role of the machine
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Name = var.name
    }
  }
}
