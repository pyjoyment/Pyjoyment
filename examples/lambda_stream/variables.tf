variable "name" {
  description = "The name of the function and of the other resources"
  type        = string
  default     = "pyjoyment-stream"
}

variable "region" {
  description = "The region, or the one of the default chain of AWS"
  type        = string
  default     = null
}

variable "aws_profile" {
  description = "The profile of AWS of the credentials and the region, or the one of the default chain of AWS"
  type        = string
  default     = null
}

variable "runtime" {
  description = "The runtime of Python of the function, the one of \"generate lambda-zip --runtime\""
  type        = string
  default     = "python3.15"
}

variable "pyjoyment_layer" {
  description = "The ARN of a published layer of Pyjoyment, in the place of the public one or of function/dist/pyjoyment.zip"
  type        = string
  default     = null
}

variable "public_layers" {
  description = "Take the public layer of Pyjoyment of Pyjoyment-Lambda-Layers, for a build with \"--function-only\", or the layer of function/dist"
  type        = bool
  default     = true
}

variable "pyjoyment_version" {
  description = "The version of Pyjoyment of the public layers, as \"0.3.0\", the one that \"--function-only\" tells, or the latest one"
  type        = string
  default     = null
}
