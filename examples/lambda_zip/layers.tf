# The index of the public layers of the latest release of Pyjoyment-Lambda-Layers, {layer: {region: arn}}, behind a
# redirection of GitHub, which the provider follows
data "http" "layers" {
  url = "https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/releases/latest/download/layers.json"

  lifecycle {
    enabled = var.public_layers
  }
}

# The names of the layers of the version of Python, as python3_15-arm64 and pyjoyment-python3_15
locals {
  public_layers = var.public_layers ? jsondecode(data.http.layers.response_body) : {}
  python_name   = "python${replace(var.python, ".", "_")}"
}
