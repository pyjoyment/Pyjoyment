variable "name" {
  description = "The name of the function and of the other resources"
  type        = string
  default     = "pyjoyment-zip"
}

variable "region" {
  description = "The region, or the one of the default chain of AWS"
  type        = string
  default     = null
}

variable "pyjoyment_layer" {
  description = "The ARN of a published layer of Pyjoyment, in the place of function/dist/pyjoyment.zip"
  type        = string
  default     = null
}

variable "public_layers" {
  description = "Take the public layers of Pyjoyment-Lambda-Layers, for a build with \"--function-only\", or the layers of function/dist"
  type        = bool
  default     = true
}

variable "python" {
  description = "The version of Python of the public layers, as \"3.14\" or \"3.15t\""
  type        = string
  default     = "3.14"
}

variable "arch" {
  description = "The architecture of the function, the one of \"generate lambda-zip --arch\""
  type        = string
  default     = "arm64"

  validation {
    condition     = contains(["arm64", "x86_64"], var.arch)
    error_message = "The architecture is \"arm64\" or \"x86_64\"."
  }
}

variable "invoke_mode" {
  description = "The invoke mode of the Function URL, BUFFERED or RESPONSE_STREAM"
  type        = string
  default     = "BUFFERED"

  validation {
    condition     = contains(["BUFFERED", "RESPONSE_STREAM"], var.invoke_mode)
    error_message = "The invoke mode is \"BUFFERED\" or \"RESPONSE_STREAM\"."
  }
}
