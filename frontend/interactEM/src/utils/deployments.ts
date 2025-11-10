import type { PipelineDeploymentState } from "../client"

export const getDeploymentStateColor = (
  state: PipelineDeploymentState,
): "default" | "primary" | "secondary" | "error" => {
  const STATE_COLORS: Record<
    PipelineDeploymentState,
    "default" | "primary" | "secondary" | "error"
  > = {
    pending: "secondary",
    running: "primary",
    cancelled: "default",
    failed_to_start: "error",
    failure_on_agent: "error",
    assigned_agents: "secondary",
  }

  return STATE_COLORS[state] || "default"
}

export const isActiveDeploymentState = (
  state: PipelineDeploymentState,
): boolean => {
  return state === "running" || state === "pending"
}

export const formatDeploymentState = (
  state: PipelineDeploymentState,
): string => {
  return state.replace("_", " ")
}
