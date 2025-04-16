import { AgentStatus } from "../types/agent"

export function getAgentStatusColor(
  status: AgentStatus,
): "info" | "success" | "warning" | "error" | "default" {
  switch (status) {
    case AgentStatus.INITIALIZING:
      return "info"
    case AgentStatus.IDLE:
      return "success"
    case AgentStatus.BUSY:
      return "warning"
    case AgentStatus.ERROR:
      return "error"
    case AgentStatus.SHUTTING_DOWN:
      return "default"
    default:
      return "default"
  }
}
