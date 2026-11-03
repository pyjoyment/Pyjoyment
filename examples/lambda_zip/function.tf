# The ZIP files of "generate lambda-zip" in the directory of the function: the layers with Python and with Pyjoyment,
# which Lambda unpacks in /opt, and the function with the application and the bootstrap that runs it, which are the
# same for the same files, so that a new build changes only what has changed
locals {
  dist = "${path.module}/function/dist"
}

# The layer of Python, unless the function takes the public one
resource "aws_lambda_layer_version" "python" {
  count = var.public_layers ? 0 : 1

  layer_name               = "${var.name}-python"
  filename                 = "${local.dist}/python.zip"
  source_code_hash         = filebase64sha256("${local.dist}/python.zip")
  compatible_runtimes      = ["provided.al2023"]
  compatible_architectures = [var.arch]
}

# The layer of Pyjoyment, in the site-packages of the Python of the function, unless the variable "pyjoyment_layer"
# names one that is published already or the function takes the public one
resource "aws_lambda_layer_version" "pyjoyment" {
  count = var.pyjoyment_layer == null && !var.public_layers ? 1 : 0

  layer_name               = "${var.name}-pyjoyment"
  filename                 = "${local.dist}/pyjoyment.zip"
  source_code_hash         = filebase64sha256("${local.dist}/pyjoyment.zip")
  compatible_runtimes      = ["provided.al2023"]
  compatible_architectures = [var.arch]
}

locals {
  region = data.aws_region.current.region
  python_layer = (
    var.public_layers ? local.public_layers["${local.python_name}-${var.arch}"][local.region]
    : aws_lambda_layer_version.python[0].arn
  )
  pyjoyment_layer = (
    var.pyjoyment_layer != null ? var.pyjoyment_layer
    : var.public_layers ? local.public_layers["pyjoyment-${local.python_name}"][local.region]
    : aws_lambda_layer_version.pyjoyment[0].arn
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

# The custom runtime, whose bootstrap runs the script, which is the runtime of the function itself, with the handler of
# the script, which the provider requires and the bootstrap does not need
resource "aws_lambda_function" "function" {
  function_name    = var.name
  role             = aws_iam_role.function.arn
  runtime          = "provided.al2023"
  architectures    = [var.arch]
  handler          = "app.handler"
  filename         = "${local.dist}/function.zip"
  source_code_hash = filebase64sha256("${local.dist}/function.zip")
  layers           = [local.python_layer, local.pyjoyment_layer]
  memory_size      = 128
  timeout          = 10

  environment {
    variables = {
      # The invoke mode of the Function URL, which the function does not learn from its invocations
      PYJO_LAMBDA_INVOKE_MODE = var.invoke_mode

      PYJO_MODE = "development"
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.function.name
  }

  depends_on = [aws_iam_role_policy_attachment.function]
}
