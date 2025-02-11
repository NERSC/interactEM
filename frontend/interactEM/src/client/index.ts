export * from "./generated"
export * from "./generated/@tanstack/react-query.gen"
export * from "./generated/client.gen"
import { z } from "zod"
import { zAgentCreateEvent as zAgentCreateEventTmp } from "./generated/zod.gen"

export const zAgentCreateEvent = zAgentCreateEventTmp.extend({
  duration: z.string().time(),
  num_nodes: z.coerce.number().int(),
})
