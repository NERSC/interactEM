// frontend/interactEM/src/types/agent.ts
import { z } from "zod"

export enum AgentStatus {
  INITIALIZING = "initializing",
  IDLE = "idle",
  BUSY = "busy",
  ERROR = "error",
  SHUTTING_DOWN = "shutting_down",
}

export enum URILocation {
  operator = "operator",
  port = "port",
  agent = "agent",
  orchestrator = "orchestrator",
}

export const AgentSchema = z.object({
  name: z.string().nullable().optional(),
  uri: z.object({
    id: z.string(),
    location: z.nativeEnum(URILocation),
    hostname: z.string(),
    comm_backend: z.string(),
    query: z.record(z.any()).optional(),
  }),
  status: z.nativeEnum(AgentStatus),
  status_message: z.string().nullable().optional(),
  tags: z.array(z.string()).default([]),
  networks: z.array(z.string()).default([]),
  pipeline_id: z.string().nullable().optional(),
  operator_assignments: z.array(z.string()).nullable().optional(), // New nullable field
  uptime: z.number(),
  error_messages: z
    .array(
      z.object({
        message: z.string(),
        timestamp: z.number(),
      }),
    )
    .default([]),
})

export type Agent = z.infer<typeof AgentSchema>
