import type { Consumer, ConsumerConfig } from "@nats-io/jetstream"
import { JetStreamError } from "@nats-io/jetstream"
import { DrainingConnectionError } from "@nats-io/nats-core/internal"
import { useEffect, useRef, useState } from "react"
import { useNats } from "../../contexts/nats"

interface UseConsumerOptions {
  stream: string
  config: ConsumerConfig | null
}

export const useConsumer = ({
  stream,
  config,
}: UseConsumerOptions): Consumer | null => {
  const { jetStreamClient, jetStreamManager } = useNats()
  const [consumer, setConsumer] = useState<Consumer | null>(null)
  const isMounted = useRef(true)
  // Ref to hold the current consumer instance across renders
  const consumerRef = useRef<Consumer | null>(null)

  useEffect(() => {
    // Mark component as mounted when effect runs
    isMounted.current = true

    // If config is null, clear the consumer
    if (!config) {
      const consumerToDelete = consumerRef.current
      if (consumerToDelete) {
        consumerToDelete.delete().catch((error) => {
          if (!(error instanceof DrainingConnectionError)) {
            console.error("Error deleting consumer:", error)
          }
        })
        consumerRef.current = null
      }
      setConsumer(null)
      return
    }

    const deleteConsumer = async (consumerToDelete: Consumer | null) => {
      if (!consumerToDelete) return
      try {
        await consumerToDelete.delete()
        // If the deleted consumer is the one we created, clear the ref
        if (consumerRef.current === consumerToDelete) {
          consumerRef.current = null
        }
      } catch (error) {
        if (error instanceof DrainingConnectionError) {
          // quietly ignore if connection is draining
          return
        }
        if (error instanceof JetStreamError) {
          console.error(
            `JetStream error during consumer deletion: ${error.message}`,
          )
        } else {
          console.error(`Failed to delete consumer: ${error}`)
        }
      }
    }

    const createConsumer = async () => {
      if (!jetStreamManager || !jetStreamClient) return

      try {
        const consumerInfo = await jetStreamManager.consumers.add(
          stream,
          config,
        )
        const newConsumer = await jetStreamClient.consumers.get(
          stream,
          consumerInfo.name,
        )

        if (isMounted.current) {
          setConsumer(newConsumer)
          consumerRef.current = newConsumer
        } else {
          // If unmounted before consumer was set, delete it
          await deleteConsumer(newConsumer)
        }
      } catch (error) {
        console.error(`Failed to create consumer in stream "${stream}":`, error)
      }
    }

    createConsumer()

    return () => {
      // Mark component as unmounted
      isMounted.current = false
      const consumerToDelete = consumerRef.current

      if (consumerToDelete) {
        // Delete the consumer during cleanup
        deleteConsumer(consumerToDelete).catch((error) => {
          console.error("Error deleting consumer during cleanup:", error)
        })
      }
    }
  }, [jetStreamManager, jetStreamClient, stream, config])

  return consumer
}
