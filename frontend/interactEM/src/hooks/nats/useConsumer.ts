import type { Consumer, ConsumerConfig } from "@nats-io/jetstream"
import {
  JetStreamApiCodes,
  JetStreamApiError,
  JetStreamError,
} from "@nats-io/jetstream"
import {
  DrainingConnectionError,
  RequestError,
} from "@nats-io/nats-core/internal"
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
  const { jetStreamClient, jetStreamManager, isConnected } = useNats()
  const [consumer, setConsumer] = useState<Consumer | null>(null)
  const isMounted = useRef(true)
  // Ref to hold the current consumer instance across renders
  const consumerRef = useRef<Consumer | null>(null)

  useEffect(() => {
    // Mark component as mounted when effect runs
    isMounted.current = true

    // If not connected, skip creating consumers
    if (!isConnected) {
      return
    }

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
          if (
            createError instanceof DrainingConnectionError ||
            createError instanceof RequestError
          ) {
            // Ignore transient connection issues; will retry when connection stabilizes
            return
          }
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
  }, [jetStreamManager, jetStreamClient, stream, config, isConnected])

  return consumer
}
