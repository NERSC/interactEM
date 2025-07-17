import { AgentStatus } from "../types/gen"

export function getAgentStatusColor(
  status: AgentStatus,
): "info" | "success" | "warning" | "error" | "default" {
  switch (status) {
    case AgentStatus.initializing:
      return "info"
    case AgentStatus.idle:
      return "success"
    case AgentStatus.busy:
      return "warning"
    case AgentStatus.error:
      return "error"
    case AgentStatus.shutting_down:
      return "default"
    default:
      return "default"
  }
}
