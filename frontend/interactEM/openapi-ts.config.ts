import { defineConfig, defaultPlugins } from "@hey-api/openapi-ts"

export default defineConfig({
  client: "@hey-api/client-axios",
  input: "openapi.json",
  output: {
    format: "biome",
    path: "src/client/generated",
  },
  plugins: [...defaultPlugins, "@tanstack/react-query", "zod"],
})
