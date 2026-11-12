# The ZIP files of "generate lambda-zip --runtime" in the directory of the function: the layer with Pyjoyment, which
# Lambda unpacks in /opt, and the function with the application and the wrapper that runs its runtime client, which are
# the same for the same files, so that a new build changes only what has changed
locals {
  dist = "${path.module}/function/dist"

  # The layer of the build, whose ZIP file is hashed only then, as OpenTofu validates the resources that are not
  # enabled too, and "--function-only" writes no layer
  pyjoyment_build = var.pyjoyment_layer == null && !var.public_layers
}

# The layer of Pyjoyment, in the site-packages of the Python of the function, unless the variable "pyjoyment_layer"
# names one that is published already or the function takes the public one
resource "aws_lambda_layer_version" "pyjoyment" {
  layer_name               = "${var.name}-pyjoyment"
  filename                 = "${local.dist}/pyjoyment.zip"
  source_code_hash         = local.pyjoyment_build ? filebase64sha256("${local.dist}/pyjoyment.zip") : null
  compatible_runtimes      = [var.runtime]
  compatible_architectures = ["arm64"]

  lifecycle {
    enabled = local.pyjoyment_build
  }
}

locals {
  pyjoyment_layer = (
    var.pyjoyment_layer != null ? var.pyjoyment_layer
    : var.public_layers ? local.public_layers[local.pyjoyment_name][data.aws_region.current.region]
    : aws_lambda_layer_version.pyjoyment.arn
  )
}

resource "aws_iam_role" "function" {
  name = var.name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "function" {
  role       = aws_iam_role.function.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "function" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = 1
}

resource "aws_lambda_function" "function" {
  function_name    = var.name
  role             = aws_iam_role.function.arn
  runtime          = var.runtime
  architectures    = ["arm64"]
  handler          = "app.handler"
  filename         = "${local.dist}/function.zip"
  source_code_hash = filebase64sha256("${local.dist}/function.zip")
  layers           = [local.pyjoyment_layer]
  memory_size      = 128
  timeout          = 10

  environment {
    variables = {
      # The runtime client of Pyjo.Server.Lambda in the place of the one of the runtime, which does not stream
      AWS_LAMBDA_EXEC_WRAPPER = "/var/task/wrapper.py"

      # The invoke mode of the Function URL, which the function does not learn from its invocations
      PYJO_LAMBDA_INVOKE_MODE = "RESPONSE_STREAM"

      PYJO_MODE = "development"

      # The site-packages of the layer, which the runtime puts in the path of its own runtime client only, and not of
      # the one of the wrapper
      PYTHONPATH = "/opt/python/lib/${var.runtime}/site-packages"
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.function.name
  }

  depends_on = [aws_iam_role_policy_attachment.function]
}
