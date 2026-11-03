# The index of the public layers of the latest release of Pyjoyment-Lambda-Layers, {layer: {region: arn}}, behind a
# redirection of GitHub, which the provider follows
data "http" "layers" {
  count = var.public_layers ? 1 : 0

  url = "https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/releases/latest/download/layers.json"
}

# The names of the layers of the version of Python, as python3_14-arm64 and pyjoyment-python3_14
locals {
  public_layers = var.public_layers ? jsondecode(data.http.layers[0].response_body) : {}
  python_name   = "python${replace(var.python, ".", "_")}"
}
