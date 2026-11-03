# An Application Load Balancer on a public address, with the name of AWS, as there is no domain of its own, and so
# HTTP without TLS, with "-var alb=true"
resource "aws_security_group" "alb" {
  name   = "${var.name}-alb"
  vpc_id = data.aws_vpc.default.id

  lifecycle {
    enabled = var.alb
  }
}

resource "aws_vpc_security_group_ingress_rule" "http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80

  lifecycle {
    enabled = var.alb
  }
}

resource "aws_lb" "this" {
  name               = var.name
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids

  lifecycle {
    enabled = var.alb
  }
}

resource "aws_lb_target_group" "function" {
  name                               = var.name
  target_type                        = "lambda"
  lambda_multi_value_headers_enabled = var.multi_value_headers

  lifecycle {
    enabled = var.alb
  }
}

resource "aws_lambda_permission" "alb" {
  statement_id  = "AllowExecutionFromALB"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.function.function_name
  principal     = "elasticloadbalancing.amazonaws.com"
  source_arn    = aws_lb_target_group.function.arn

  lifecycle {
    enabled = var.alb
  }
}

resource "aws_lb_target_group_attachment" "function" {
  target_group_arn = aws_lb_target_group.function.arn
  target_id        = aws_lambda_function.function.arn

  depends_on = [aws_lambda_permission.alb]

  lifecycle {
    enabled = var.alb
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.function.arn
  }

  lifecycle {
    enabled = var.alb
  }
}
