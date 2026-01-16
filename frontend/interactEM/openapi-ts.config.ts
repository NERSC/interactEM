import { defaultPlugins, defineConfig } from "@hey-api/openapi-ts"

export default defineConfig({
  input: "openapi.json",
  output: {
    path: "src/client/generated",
  },
  postProcess: ["biome:format"],
  plugins: [
    ...defaultPlugins,
    "@hey-api/client-axios",
    "@tanstack/react-query",
    "zod",
  ],
})
