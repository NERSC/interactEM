import { z } from "zod"
import {
  AgentStatus,
  type AgentVal,
  CommBackend,
  type ErrorMessage,
  type URI,
  URILocation,
} from "./gen"

const zURI = z.object({
  id: z.string(),
  location: z.nativeEnum(URILocation),
  hostname: z.string(),
  comm_backend: z.nativeEnum(CommBackend),
  query: z.record(z.string(), z.array(z.string())).optional(),
}) satisfies z.ZodType<URI>

// For AgentErrorMessage, handle manually due to index signature
const zErrorMessage = z.object({
  message: z.string(),
  timestamp: z.number(),
}) satisfies z.ZodType<ErrorMessage>

export const AgentValSchema = z.object({
  name: z.string().nullable().optional(),
  uri: zURI,
  status: z.nativeEnum(AgentStatus),
  status_message: z.string().nullable().optional(),
  tags: z.array(z.string()).optional(),
  networks: z.array(z.string()),
  pipeline_id: z.string().nullable().optional(),
  operator_assignments: z.array(z.string()).nullable().optional(),
  uptime: z.number(),
  error_messages: z.array(zErrorMessage).optional(),
}) satisfies z.ZodType<AgentVal>

// Re-export this because AgentVal is an interface and we need this for
// the AgentNode type
export type AgentValType = z.infer<typeof AgentValSchema>
