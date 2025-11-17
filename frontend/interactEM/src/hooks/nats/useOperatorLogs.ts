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
  const { operators: allOperators } = useOperatorsByCanonicalId(
    canonicalOperatorId,
    true,
  )

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
    if (!deploymentIdOrActiveId) {
      return null
    }

    // Use consistent durable name for the deployment to avoid duplicate consumers
    const durableName = `operator-logs-${deploymentIdOrActiveId}`

    // If we have no operators, use wildcard pattern to fetch historical logs
    if (sortedOperatorIds.length === 0) {
      return {
        filter_subjects: [
          `${SUBJECT_LOGS_DEPLOYMENTS}.${deploymentIdOrActiveId}.${OPERATORS}.>`,
        ],
        deliver_policy: DeliverPolicy.All,
        ack_policy: AckPolicy.All,
        replay_policy: ReplayPolicy.Instant,
        durable_name: durableName,
      }
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
      durable_name: durableName,
    }
  }, [deploymentIdOrActiveId, sortedOperatorIds])

  const consumer = useConsumer({ stream: STREAM_LOGS, config })

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
