import type { JsMsg } from "@nats-io/jetstream"
import { AckPolicy, DeliverPolicy, ReplayPolicy } from "@nats-io/jetstream"
import { useCallback, useMemo, useState } from "react"
import { useConsumeMessages } from "./useConsumeMessages"
import { useConsumer } from "./useConsumer"
import { useStream } from "./useStream"

interface UseStreamMessageOptions<T> {
  streamName: string
  streamConfig: {
    name: string
    subjects: string[]
    max_msgs_per_subject?: number
  }
  subject: string
  deliverPolicy?: DeliverPolicy
  initialValue?: T | null
  transform?: (data: any, originalMessage: JsMsg) => T | null
}

export function useStreamMessage<T>({
  streamName,
  streamConfig,
  subject,
  deliverPolicy = DeliverPolicy.LastPerSubject,
  initialValue = null,
  transform,
}: UseStreamMessageOptions<T>) {
  const [data, setData] = useState<T | null>(initialValue)
  const [hasReceivedMessage, setHasReceivedMessage] = useState<boolean>(false)

  // Ensure stream exists
  useStream(streamConfig)

  const consumerConfig = useMemo(
    () => ({
      filter_subjects: [subject],
      deliver_policy: deliverPolicy,
      ack_policy: AckPolicy.Explicit,
      replay_policy: ReplayPolicy.Instant,
    }),
    [subject, deliverPolicy],
  )

  const consumer = useConsumer({
    stream: streamName,
    config: consumerConfig,
  })

  const handleMessage = useCallback(
    async (m: JsMsg) => {
      try {
        let transformedData: T | null = null

        if (transform) {
          // Pass both parsed data and original message to transform function
          try {
            const jsonData = m.json<any>()
            transformedData = transform(jsonData, m)
          } catch (parseError) {
            // If JSON parsing fails, still give transform a chance with original message
            transformedData = transform(null, m)
          }
        } else {
          // Default behavior is to parse as JSON
          transformedData = m.json<T>()
        }

        if (transformedData !== null) {
          setData((prevData) => {
            // For binary data, can't use JSON.stringify comparison
            const isBinary = transformedData instanceof Uint8Array
            const isEqual = isBinary
              ? prevData instanceof Uint8Array &&
                prevData.length === (transformedData as Uint8Array).length
              : JSON.stringify(transformedData) === JSON.stringify(prevData)

            return isEqual ? prevData : transformedData
          })
        }

        setHasReceivedMessage(true)
      } catch (error) {
        console.error(`Error processing message for ${subject}:`, error)
      }
    },
    [subject, transform],
  )

  useConsumeMessages({
    consumer,
    handleMessage,
  })

  return { data, hasReceivedMessage }
}
