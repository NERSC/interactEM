target "output" { 
  output = [
    {
      type="image",
      push-by-digest=true,
      name-canonical=true,
      push=true
    }
  ]
}