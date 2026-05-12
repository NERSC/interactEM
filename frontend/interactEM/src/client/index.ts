export * from "./generated"
export * from "./generated/@tanstack/react-query.gen"
export { createClient } from "./generated/client"
export * from "./generated/client.gen"

import { z } from "zod"
import {
  zAgentCreateEvent as zAgentCreateEventTmp,
  zPipelineCreate as zPipelineCreateTmp,
  zPipelinePublic as zPipelinePublicTmp,
  zPipelineRevisionCreate as zPipelineRevisionCreateTmp,
  zPipelinesPublic as zPipelinesPublicTmp,
  zPipelineUpdate as zPipelineUpdateTmp,
} from "./generated/zod.gen"

export const zAgentCreateEvent = zAgentCreateEventTmp.extend({
  duration: z.string().time(),
  num_nodes: z.coerce.number().int(),
  gpus_per_node: z.coerce.number().int().positive().optional().nullable(),
})

// This is a workaround for the generated data field being an object.
// This removes the actual data when it is parsed. Could be changed
// if we added something other than a json blob to our pipeline.
const zPipelineData = z.record(z.unknown())

export const zPipelineCreate = zPipelineCreateTmp.extend({
  data: zPipelineData,
})
export const zPipelinePublic = zPipelinePublicTmp.extend({
  data: zPipelineData,
})
export const zPipelinesPublic = zPipelinesPublicTmp.extend({
  data: z.array(zPipelinePublic),
})
export const zPipelineRevisionCreate = zPipelineRevisionCreateTmp.extend({
  data: zPipelineData,
})
export const zPipelineUpdate = zPipelineUpdateTmp.extend({
  data: zPipelineData,
})
