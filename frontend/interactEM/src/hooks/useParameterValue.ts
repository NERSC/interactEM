import { useState, useMemo, useCallback } from "react"
import { AckPolicy, DeliverPolicy, ReplayPolicy } from "@nats-io/jetstream"
import { useConsumer } from "./useConsumer"
import { useConsumeMessages } from "./useConsumeMessages"
import { PARAMETERS_STREAM, PARAMETERS_UPDATE_STREAM } from "../constants/nats"
import type { JsMsg } from "@nats-io/jetstream"
import { useStream } from "./useStream"

const streamConfig = {
  name: PARAMETERS_STREAM,
  subjects: [`${PARAMETERS_STREAM}.>`],
}

export const useParameterValue = (
  operatorID: string,
  name: string,
  defaultValue: string,
): { actualValue: string; hasReceivedMessage: boolean } => {
  const subject = `${PARAMETERS_UPDATE_STREAM}.${operatorID}.${name}`

  const config = useMemo(
    () => ({
      filter_subjects: [subject],
      deliver_policy: DeliverPolicy.LastPerSubject,
      ack_policy: AckPolicy.Explicit,
      replay_policy: ReplayPolicy.Instant,
    }),
    [subject],
  )

  // ensure stream
  useStream(streamConfig)

  const consumer = useConsumer({
    stream: PARAMETERS_STREAM,
    config,
  })

  const [actualValue, setActualValue] = useState<string>(defaultValue)
  const [hasReceivedMessage, setHasReceivedMessage] = useState<boolean>(false)

  const handleMessage = useCallback(async (m: JsMsg) => {
    const value = m.json<string>()
    setActualValue(value)
    setHasReceivedMessage(true)
  }, [])

  useConsumeMessages({ consumer, handleMessage })

  return { actualValue, hasReceivedMessage }
}
