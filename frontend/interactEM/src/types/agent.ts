// frontend/interactEM/src/types/agent.ts
import { z } from "zod"

export enum AgentStatus {
  INITIALIZING = "initializing",
  IDLE = "idle",
  BUSY = "busy",
  ERROR = "error",
  SHUTTING_DOWN = "shutting_down",
}

enum URILocation {
  operator = "operator",
  port = "port",
  agent = "agent",
  orchestrator = "orchestrator",
}

enum CommBackend {
  zmq = "zmq",
  nats = "nats",
  mpi = "mpi",
}

const URI = z.object({
  id: z.string(),
  location: z.nativeEnum(URILocation),
  hostname: z.string(),
  comm_backend: z.nativeEnum(CommBackend),
  query: z.record(z.any()).optional(),
})

const ErrorMessage = z.object({
  message: z.string(),
  timestamp: z.number(),
})

export const AgentValSchema = z.object({
  name: z.string().nullable().optional(),
  uri: URI,
  status: z.nativeEnum(AgentStatus),
  status_message: z.string().nullable().optional(),
  tags: z.array(z.string()).default([]).optional(),
  networks: z.array(z.string()).default([]).optional(),
  pipeline_id: z.string().nullable().optional(),
  operator_assignments: z.array(z.string()).nullable().optional(),
  uptime: z.number(),
  error_messages: z.array(ErrorMessage).default([]).optional(),
})

export type AgentVal = z.infer<typeof AgentValSchema>
export type Agent = AgentVal
