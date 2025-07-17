import type { PipelineDeploymentState } from "../client"

export const getDeploymentStateColor = (
  state: PipelineDeploymentState,
): "default" | "primary" | "error" => {
  const STATE_COLORS: Record<
    PipelineDeploymentState,
    "default" | "primary" | "error"
  > = {
    pending: "default",
    running: "primary",
    cancelled: "default",
    failed_to_start: "error",
  }

  return STATE_COLORS[state] || "default"
}

export const isActiveDeploymentState = (state: PipelineDeploymentState): boolean => {
  return state === "running" || state === "pending"
}

export const formatDeploymentState = (state: PipelineDeploymentState): string => {
  return state.replace("_", " ")
}
