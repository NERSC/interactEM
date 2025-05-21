import type { JsMsg } from "@nats-io/jetstream"
import { AckPolicy, DeliverPolicy, ReplayPolicy } from "@nats-io/jetstream"
import { useCallback, useMemo, useState } from "react"
import { OPERATORS_STREAM } from "../../constants/nats"
import type { OperatorEvent } from "../../types/events"
import { useConsumeMessages } from "./useConsumeMessages"
import { useConsumer } from "./useConsumer"
import { useStream } from "./useStream"

const streamConfig = {
  name: OPERATORS_STREAM,
  subjects: [`${OPERATORS_STREAM}.>`],
}

export const useOperatorEvents = (operatorID: string) => {
  const subject = `${OPERATORS_STREAM}.${operatorID}.events`

  const config = useMemo(
    () => ({
      filter_subjects: [subject],
      deliver_policy: DeliverPolicy.Last,
      ack_policy: AckPolicy.Explicit,
      replay_policy: ReplayPolicy.Instant,
    }),
    [subject],
  )

  // ensure stream
  useStream(streamConfig)

  const consumer = useConsumer({
    stream: OPERATORS_STREAM,
    config,
  })

  const [operatorEvent, setOperatorEvent] = useState<OperatorEvent | null>(null)

  const handleMessage = useCallback(async (m: JsMsg) => {
    try {
      const eventData = m.json<OperatorEvent>()
      setOperatorEvent(eventData)
    } catch (e) {
      console.error("Failed to parse operator event data", e)
    }
  }, [])

  useConsumeMessages({ consumer, handleMessage })

  return { operatorEvent }
}
