import { AckPolicy, DeliverPolicy, ReplayPolicy } from "@nats-io/jetstream"
import { useCallback, useMemo, useState } from "react"
import {
  OPERATORS,
  STREAM_LOGS,
  SUBJECT_LOGS_DEPLOYMENTS,
} from "../../constants/nats"
import type { OperatorLog } from "../../types/gen"
import { useActivePipeline } from "../api/useActivePipeline"
import { useConsumeMessages } from "./useConsumeMessages"
import { useConsumer } from "./useConsumer"
import { useOperatorsByCanonicalId } from "./useOperatorStatus"

interface UseOperatorLogsOptions {
  canonicalOperatorId: string
  deploymentId?: string
}

export function useOperatorLogs({
  canonicalOperatorId,
  deploymentId,
}: UseOperatorLogsOptions) {
  const { runtimePipelineId } = useActivePipeline()
  const { operators: allOperators } =
    useOperatorsByCanonicalId(canonicalOperatorId)

  // We may want to pass in deploymentId in the future to look at
  // historical logs, but in current impl we just use active pipeline ID
  const deploymentIdOrActiveId = deploymentId || runtimePipelineId

  const operators = useMemo(
    () =>
      allOperators.filter(
        (op) =>
          op.runtime_pipeline_id === deploymentIdOrActiveId ||
          !deploymentIdOrActiveId,
      ),
    [allOperators, deploymentIdOrActiveId],
  )

  const sortedOperatorIds = useMemo(
    () => operators.map((op) => op.id).sort(),
    [operators],
  )
  const [logs, setLogs] = useState<OperatorLog[]>([])

  const config = useMemo(() => {
    if (sortedOperatorIds.length === 0) {
      return null
    }

    const subjects = sortedOperatorIds.map(
      (id) =>
        `${SUBJECT_LOGS_DEPLOYMENTS}.${deploymentIdOrActiveId}.${OPERATORS}.${id}`,
    )

    return {
      filter_subjects: subjects,
      deliver_policy: DeliverPolicy.All,
      ack_policy: AckPolicy.All,
      replay_policy: ReplayPolicy.Instant,
      durable_name: `operator-logs-${deploymentIdOrActiveId}-${sortedOperatorIds.join("-")}`,
    }
  }, [deploymentIdOrActiveId, sortedOperatorIds])

  const consumer = config ? useConsumer({ stream: STREAM_LOGS, config }) : null

  const handleMessage = useCallback((msg: any) => {
    try {
      setLogs((prevLogs) => [...prevLogs, msg.json() as OperatorLog])
    } catch (error) {
      console.error("Error parsing operator log message:", error)
    }
  }, [])

  useConsumeMessages({ consumer, handleMessage })
  return { logs, operators }
}
