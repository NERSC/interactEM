// For CI push-by-digest builds, override generate_tags() to use minimal tags
// Full tags are applied later via docker buildx imagetools in merge-manifests

function "generate_tags" {
  params = [service_name]
  result = ["${REGISTRY}/${service_name}"]
}
