export * from "./generated"
export * from "./generated/@tanstack/react-query.gen"
import { z } from "zod"
import { zAgentCreateEvent } from "./generated/zod.gen"

export const zAgentCreateEventWithDuration = zAgentCreateEvent.extend({
  duration: z.string().time(),
})
