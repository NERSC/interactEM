import { AckPolicy, DeliverPolicy, ReplayPolicy } from "@nats-io/jetstream"
import { NatsError } from "@nats-io/nats-core"
import { useEffect, useMemo, useState } from "react"
import { IMAGES_STREAM } from "../constants/nats"
import { useConsumer } from "./useConsumer"
import { useStream } from "./useStream"

export const useImage = (operatorID: string): Uint8Array | null => {
  const subject = `${IMAGES_STREAM}.${operatorID}`

  const streamConfig = {
    name: IMAGES_STREAM,
    subjects: [`${IMAGES_STREAM}.>`],
    max_msgs_per_subject: 1,
  }

  const consumerConfig = useMemo(
    () => ({
      filter_subjects: [subject],
      deliver_policy: DeliverPolicy.LastPerSubject,
      ack_policy: AckPolicy.Explicit,
      replay_policy: ReplayPolicy.Instant,
    }),
    [subject],
  )

  // First ensure the stream
  useStream(streamConfig)

  const consumer = useConsumer({
    stream: IMAGES_STREAM,
    config: consumerConfig,
  })

  const [imageData, setImageData] = useState<Uint8Array | null>(null)

  useEffect(() => {
    if (!consumer) {
      return
    }

    const consumeMessages = async () => {
      const messages = await consumer.consume()
      for await (const m of messages) {
        const data = m.data
        setImageData(data)
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
          if (error instanceof NatsError) {
            if (
              error.code === "404" &&
              // TODO Lets hope the client improves!
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
  }, [consumer])

  return imageData
}
