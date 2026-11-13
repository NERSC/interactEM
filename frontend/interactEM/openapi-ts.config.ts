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
    {
      name: "zod",
      "~resolvers": {
        // zod 4's z.uuid() enforces RFC 9562 version/variant bits, but the
        // backend (Python uuid.UUID) accepts any 8-4-4-4-12 hex ID, and
        // existing operator spec IDs rely on that. z.guid() matches it.
        string: (ctx) => {
          if (ctx.schema.format !== "uuid") return undefined
          const { z } = ctx.plugin.imports
          return ctx.$(z).attr("guid").call()
        },
      },
    },
  ],
})
