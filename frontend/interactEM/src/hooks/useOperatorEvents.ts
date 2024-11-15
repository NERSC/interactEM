import { useState, useEffect, useMemo } from "react"
import { AckPolicy, DeliverPolicy, ReplayPolicy } from "@nats-io/jetstream"
import { NatsError } from "@nats-io/nats-core"
import { useConsumer } from "./useConsumer"
import { OPERATORS_STREAM } from "../constants/nats"
import type { OperatorErrorEvent, OperatorEvent } from "../types/events"
import { useNats } from "../nats/NatsContext"

export const useOperatorEvents = (operatorID: string) => {
  const { jc } = useNats()
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
          const eventData = jc.decode(m.data) as OperatorEvent    

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
        try {
          const info = await consumer.info()
          if (info.stream_name) {
            await consumer.delete()
          }
        } catch (error: any) {
          if (error instanceof NatsError) {
            if (
              error.code === "404" &&
              error.message.includes("consumer not found")
            ) {
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
  }, [consumer, jc])

  return { operatorErrorEvent, isError }
}
