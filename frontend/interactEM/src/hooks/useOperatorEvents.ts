import { useState, useEffect, useMemo } from "react"
import {
  AckPolicy,
  DeliverPolicy,
  JetStreamError,
  ReplayPolicy,
  JetStreamApiError,
  JetStreamApiCodes,
} from "@nats-io/jetstream"
import { useConsumer } from "./useConsumer"
import { OPERATORS_STREAM } from "../constants/nats"
import type { OperatorErrorEvent, OperatorEvent } from "../types/events"

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

  const consumer = useConsumer({
    stream: OPERATORS_STREAM,
    config,
  })

  const [operatorErrorEvent, setOperatorErrorEvent] =
    useState<OperatorErrorEvent | null>(null)
  const [isError, setIsError] = useState<boolean>(false)

  useEffect(() => {
    if (!consumer) {
      return
    }

    const consumeMessages = async () => {
      const messages = await consumer.consume()
      for await (const m of messages) {
        try {
          const eventData = m.json<OperatorEvent>()

          if (eventData.type === "error") {
            const errorEvent = eventData as OperatorErrorEvent
            setOperatorErrorEvent(errorEvent)
            setIsError(true)
          } else if (eventData.type === "running") {
            setOperatorErrorEvent(null)
            setIsError(false)
          }
        } catch (e) {
          console.error("Failed to parse operator event data", e)
        } finally {
          m.ack()
        }
      }
    }

    consumeMessages()

    return () => {
      const deleteConsumer = async () => {
        if (consumer) {
          try {
            await consumer.delete()
          } catch (error) {
            if (error instanceof JetStreamApiError) {
              if (error.code === JetStreamApiCodes.ConsumerNotFound) {
                return
              } else {
                console.error(
                  `JetStream error during consumer deletion: ${error.message}`,
                )
                return
              }
            } else if (error instanceof JetStreamError) {
              console.error(
                `JetStream error during consumer deletion: ${error.message}`,
              )
            } else {
              console.error(`Failed to delete consumer: ${error}`)
            }
          }
        }
      }

      deleteConsumer()
    }
  }, [consumer])

  return { operatorErrorEvent, isError }
}
