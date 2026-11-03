# The index of the public layers of the latest release of Pyjoyment-Lambda-Layers, {layer: {region: arn}}, behind a
# redirection of GitHub, which the provider follows
data "http" "layers" {
  url = "https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/releases/latest/download/layers.json"

  lifecycle {
    enabled = var.public_layers
  }
}

# The layer of Pyjoyment of the version of Python of the runtime, as pyjoyment-python3_14
locals {
  public_layers = var.public_layers ? jsondecode(data.http.layers.response_body) : {}
  python_name   = replace(var.runtime, ".", "_")
}
