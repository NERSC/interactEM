import { AckPolicy, DeliverPolicy, ReplayPolicy } from "@nats-io/jetstream"
import { useCallback, useEffect, useMemo, useState } from "react"
import { STREAM_LOGS, SUBJECT_AGENTS_LOGS } from "../../constants/nats"
import type { AgentLog } from "../../types/gen"
import { useConsumeMessages } from "./useConsumeMessages"
import { useConsumer } from "./useConsumer"

interface UseLogsOptions {
  id: string
}

export function useAgentLogs({ id }: UseLogsOptions) {
  const [logs, setLogs] = useState<AgentLog[]>([])

  const subject = `${SUBJECT_AGENTS_LOGS}.${id}`

  const config = useMemo(
    () => ({
      filter_subjects: [subject],
      deliver_policy: DeliverPolicy.All,
      ack_policy: AckPolicy.All,
      replay_policy: ReplayPolicy.Instant,
    }),
    [subject],
  )

  const consumer = useConsumer({
    stream: STREAM_LOGS,
    config,
  })

  // ensure fresh state when reopening the logs panel
  useEffect(() => {
    if (consumer) {
      setLogs([])
    }
  }, [consumer])

  const handleMessage = useCallback((msg: any) => {
    try {
      const data = msg.json() as AgentLog
      setLogs((prevLogs) => {
        return [...prevLogs, data]
      })
    } catch (error) {
      console.error("Error parsing log message:", error)
    }
  }, [])

  useConsumeMessages({
    consumer,
    handleMessage,
  })

  return { logs }
}
