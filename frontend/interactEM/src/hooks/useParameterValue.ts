import { useState, useEffect, useMemo } from "react"
import {
  AckPolicy,
  DeliverPolicy,
  JetStreamApiCodes,
  JetStreamApiError,
  ReplayPolicy,
} from "@nats-io/jetstream"
import { useConsumer } from "./useConsumer"
import { PARAMETERS_STREAM, PARAMETERS_UPDATE_STREAM } from "../constants/nats"

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

  const consumer = useConsumer({
    stream: `${PARAMETERS_STREAM}`,
    config,
  })

  const [actualValue, setActualValue] = useState<string>(defaultValue)
  const [hasReceivedMessage, setHasReceivedMessage] = useState<boolean>(false)

  useEffect(() => {
    if (!consumer) {
      return
    }

    const consumeMessages = async () => {
      const messages = await consumer.consume()
      let operatorParamValue = defaultValue
      for await (const m of messages) {
        operatorParamValue = m.json<string>()
        setActualValue(operatorParamValue)
        setHasReceivedMessage(true)
        m.ack()
      }
    }

    consumeMessages()

    return () => {
      const deleteConsumer = async () => {
        try {
          const info = await consumer.info()
          if (info.stream_name) {
            await consumer.delete()
          }
        } catch (error: any) {
          if (error instanceof JetStreamApiError) {
            if (error.code === JetStreamApiCodes.ConsumerNotFound) {
              return
            }
            console.error(`Failed to delete consumer: ${error.code}`)
          } else {
            console.error(`Failed to delete consumer: ${error.message}`)
          }
        }
      }

      deleteConsumer()
    }
  }, [consumer, defaultValue])

  return { actualValue, hasReceivedMessage }
}
