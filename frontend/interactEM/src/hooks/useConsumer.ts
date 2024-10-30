import { useState, useEffect, useRef } from "react"
import { useNats } from "../nats/NatsContext"
import type { ConsumerConfig, Consumer } from "@nats-io/jetstream"

interface UseConsumerOptions {
  stream: string
  config: ConsumerConfig
}

export const useConsumer = ({
  stream,
  config,
}: UseConsumerOptions): Consumer | null => {
  const { jetStreamClient, jetStreamManager } = useNats()
  const [consumer, setConsumer] = useState<Consumer | null>(null)
  const isMounted = useRef(true)
  const isConsumerInitialized = useRef(false)

  useEffect(() => {
    isMounted.current = true

    const createConsumer = async () => {
      if (
        jetStreamManager &&
        jetStreamClient &&
        !isConsumerInitialized.current
      ) {
        try {
          await jetStreamManager.consumers.add(stream, config)
          const newConsumer = await jetStreamClient.consumers.get(stream, {
            ...config,
          })
          if (isMounted.current) {
            setConsumer(newConsumer)
            isConsumerInitialized.current = true
          }
        } catch (createError) {
          console.error(
            `Failed to create ephemeral consumer in stream "${stream}":`,
            createError,
          )
        }
      }
    }

    createConsumer()

    return () => {
      isMounted.current = false
      if (consumer) {
        consumer.delete()
      }
    }
  }, [jetStreamManager, jetStreamClient, stream, config, consumer])

  return consumer
}
