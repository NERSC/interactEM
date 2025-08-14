import { useMemo } from "react"
import { useOperatorStatusContext } from "../../contexts/nats/operatorstatus"
import { OperatorStatus } from "../../types/gen"

export const useOperatorStatus = (operatorId?: string) => {
  const { operators, operatorsLoading, operatorsError } =
    useOperatorStatusContext()

  const operator = useMemo(
    () =>
      operatorId ? operators.find((op) => op.id === operatorId) || null : null,
    [operators, operatorId],
  )

  return {
    operator,
    isLoading: operatorsLoading,
    error: operatorsError,
  }
}

export const useAllOperatorStatuses = () => {
  const { operators, operatorsLoading, operatorsError } =
    useOperatorStatusContext()

  return {
    operators,
    isLoading: operatorsLoading,
    error: operatorsError,
  }
}

export const useOperatorsByCanonicalId = (canonicalId: string) => {
  const { operators, operatorsLoading, operatorsError } =
    useOperatorStatusContext()

  const matchingOperators = useMemo(
    () => operators.filter((op) => op.canonical_id === canonicalId),
    [operators, canonicalId],
  )

  return {
    operators: matchingOperators,
    isLoading: operatorsLoading,
    error: operatorsError,
  }
}

export const useAggregateOperatorStatus = (canonicalId?: string) => {
  const { operators, isLoading, error } = useOperatorsByCanonicalId(
    canonicalId || "",
  )
  const status: OperatorStatus | null = useMemo(() => {
    if (operators.length === 0) return null

    const statuses = operators.map((op) => op.status)
    if (statuses.every((s) => s === OperatorStatus.running))
      return OperatorStatus.running
    if (statuses.some((s) => s === OperatorStatus.error))
      return OperatorStatus.error
    if (statuses.some((s) => s === OperatorStatus.shutting_down))
      return OperatorStatus.shutting_down
    return OperatorStatus.initializing
  }, [operators])

  return {
    status,
    isLoading,
    error,
  }
}

export const useOperatorsByPipelineId = (pipelineId?: string) => {
  const { operators, operatorsLoading, operatorsError } =
    useOperatorStatusContext()

  const matchingOperators = useMemo(
    () => operators.filter((op) => op.runtime_pipeline_id === pipelineId),
    [operators, pipelineId],
  )

  return {
    operators: matchingOperators,
    isLoading: operatorsLoading,
    error: operatorsError,
  }
}

export const useRuntimeOperatorStatusStyles = (canonicalId: string) => {
  const { status } = useAggregateOperatorStatus(canonicalId)

  const getStatusClass = (status: OperatorStatus | null) => {
    switch (status) {
      case OperatorStatus.initializing:
        return "operator-status-initializing"
      case OperatorStatus.running:
        return "operator-status-running"
      case OperatorStatus.shutting_down:
        return "operator-status-shutting-down"
      default:
        return "operator-status-offline"
    }
  }

  return {
    status,
    statusClass: getStatusClass(status),
    isOnline: status === "running",
    isInitializing: status === "initializing",
  }
}
