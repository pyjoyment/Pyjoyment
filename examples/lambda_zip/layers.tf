# The releases of Pyjoyment-Lambda-Layers, for the public layers of a version of Pyjoyment, whose tags have the version
# and the date, as 0.3.0+2026.11.05, as GitHub has no latest release of a prefix. The API of GitHub answers 60 requests
# an hour of an address without a token, and 100 releases at most, in an order of its own
data "http" "releases" {
  url = "https://api.github.com/repos/pyjoyment/Pyjoyment-Lambda-Layers/releases?per_page=100"

  request_headers = {
    Accept = "application/vnd.github+json"
  }

  lifecycle {
    enabled = var.public_layers && var.pyjoyment_version != null

    postcondition {
      condition     = self.status_code == 200
      error_message = "The API of GitHub answers ${self.status_code}: ${self.response_body}"
    }
  }
}

# The tag of the latest release of the version, the last of its releases sorted by the time of their publication
locals {
  releases = var.public_layers && var.pyjoyment_version != null ? sort([
    for release in jsondecode(data.http.releases.response_body) : "${release.published_at} ${release.tag_name}"
    if startswith(release.tag_name, "${var.pyjoyment_version}+")
  ]) : []
  release = length(local.releases) > 0 ? split(" ", local.releases[length(local.releases) - 1])[1] : null
}

# The index of the public layers of the release, {layer: {region: arn}}, or of the latest release, behind a redirection
# of GitHub, which the provider follows
data "http" "layers" {
  url = (
    local.release != null
    ? "https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/releases/download/${urlencode(local.release)}/layers.json"
    : "https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/releases/latest/download/layers.json"
  )

  lifecycle {
    enabled = var.public_layers

    precondition {
      condition     = var.pyjoyment_version == null || local.release != null
      error_message = "No release of Pyjoyment-Lambda-Layers of the latest 100 has the layers of the version of Pyjoyment, which come after its release. The variable \"public_layers\" set to false takes the layers of the build."
    }
  }
}

# The names of the layers of the version of Python, as python3_15-arm64, and pyjoyment-0_3_0-python3_15 of a version of
# Pyjoyment, or its alias pyjoyment-python3_15 in the index of the latest release
locals {
  public_layers = var.public_layers ? jsondecode(data.http.layers.response_body) : {}
  python_name   = "python${replace(var.python, ".", "_")}"
  pyjoyment_name = (
    var.pyjoyment_version != null ? "pyjoyment-${replace(var.pyjoyment_version, ".", "_")}-${local.python_name}"
    : "pyjoyment-${local.python_name}"
  )
}
