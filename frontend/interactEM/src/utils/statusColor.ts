import { AgentStatus } from "../types/gen"

export function getAgentStatusColor(
  status: AgentStatus,
): "info" | "success" | "warning" | "error" | "default" {
  switch (status) {
    case AgentStatus.initializing:
      return "info"
    case AgentStatus.idle:
      return "success"
    case AgentStatus.deployment_error:
      return "error"
    case AgentStatus.operators_starting:
      return "info"
    case AgentStatus.cleaning_operators:
      return "warning"
    case AgentStatus.assignment_received:
      return "info"
    case AgentStatus.running_deployment:
      return "success"
    case AgentStatus.shutting_down:
      return "default"
    default:
      return "default"
  }
}
