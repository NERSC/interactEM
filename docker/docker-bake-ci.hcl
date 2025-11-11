// Override platform definition for multiplatform builds in CI
target "platform" {
  platforms = ["linux/amd64", "linux/arm64"]
}
