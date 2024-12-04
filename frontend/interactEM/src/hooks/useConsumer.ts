import { useState, useEffect, useRef } from "react"
import { useNats } from "../nats/NatsContext"
import type { ConsumerConfig, Consumer } from "@nats-io/jetstream"
import {
  JetStreamApiError,
  JetStreamApiCodes,
  JetStreamError,
} from "@nats-io/jetstream"

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
  // Ref to hold the current consumer instance across renders
  const consumerRef = useRef<Consumer | null>(null)

  useEffect(() => {
    // Mark component as mounted when effect runs
    isMounted.current = true

    const deleteConsumer = async (consumerToDelete: Consumer | null) => {
      if (!consumerToDelete) return
      try {
        await consumerToDelete.delete()
        // If the deleted consumer is the one we created, clear the ref
        if (consumerRef.current === consumerToDelete) {
          consumerRef.current = null
        }
      } catch (error) {
        if (error instanceof JetStreamApiError) {
          if (error.code === JetStreamApiCodes.ConsumerNotFound) {
            return
          }
          console.error(
            `JetStream API error during consumer deletion: ${error.message}`,
          )
        } else if (error instanceof JetStreamError) {
          console.error(
            `JetStream error during consumer deletion: ${error.message}`,
          )
        } else {
          console.error(`Failed to delete consumer: ${error}`)
        }
      }
    }

    const createConsumer = async () => {
      if (jetStreamManager && jetStreamClient) {
        try {
          await jetStreamManager.consumers.add(stream, config)
          const newConsumer = await jetStreamClient.consumers.get(stream, {
            ...config,
          })

          if (isMounted.current) {
            // If component is still mounted, update state and ref
            setConsumer(newConsumer)
            consumerRef.current = newConsumer
          } else {
            // If unmounted before consumer was set, delete the consumer
            await deleteConsumer(newConsumer)
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
