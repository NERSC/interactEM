import { useMemo, useRef } from "react"
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

export const useOperatorsByCanonicalId = (
  canonicalId: string,
  stableRefOnIdOnly = false,
) => {
  const { operators, operatorsLoading, operatorsError } =
    useOperatorStatusContext()

  const prevCacheRef = useRef<string>("")
  const prevOperatorsRef = useRef<typeof operators>([])

  const matchingOperators = useMemo(() => {
    const filtered = operators.filter((op) => op.canonical_id === canonicalId)

    // Determine what to compare: just IDs or full data
    const currentCache = stableRefOnIdOnly
      ? filtered
          .map((op) => op.id)
          .sort()
          .join(",")
      : JSON.stringify(filtered)

    // If cache hasn't changed, return the previous array reference
    if (
      currentCache === prevCacheRef.current &&
      prevOperatorsRef.current.length > 0
    ) {
      return prevOperatorsRef.current
    }

    // Cache changed, update refs and return new array
    prevCacheRef.current = currentCache
    prevOperatorsRef.current = filtered
    return filtered
  }, [operators, canonicalId, stableRefOnIdOnly])

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
      case OperatorStatus.error:
        return "operator-status-error"
      default:
        return "operator-status-offline"
    }
  }

  return {
    status,
    statusClass: getStatusClass(status),
    isOnline: status === OperatorStatus.running,
    isInitializing: status === OperatorStatus.initializing,
  }
}
