import type { Consumer, ConsumerMessages, JsMsg } from "@nats-io/jetstream"
import { useEffect, useRef } from "react"

interface UseConsumeMessagesOptions {
  consumer: Consumer | null
  handleMessage: (msg: JsMsg) => Promise<void> | void
}

export const useConsumeMessages = ({
  consumer,
  handleMessage,
}: UseConsumeMessagesOptions) => {
  const handlerRef = useRef(handleMessage)

  // Update the ref when the handler changes
  useEffect(() => {
    handlerRef.current = handleMessage
  }, [handleMessage])

  // Set up the message consumption
  useEffect(() => {
    if (!consumer) return

    // Flag to handle cleanup
    let aborted = false
    // Store reference to the message iterator for cleanup
    let messagesIterator: ConsumerMessages | null = null

    // Start consuming messages
    const consumeMessages = async () => {
      try {
        messagesIterator = await consumer.consume()

        for await (const message of messagesIterator) {
          if (aborted) break

          try {
            // Use the current handler from ref
            await handlerRef.current(message)
          } catch (handlerError) {
            console.error("Error in message handler:", handlerError)
            message.term()
          }
          message.ack()
        }
      } catch (consumeError) {
        if (!aborted) {
          console.error("Error consuming messages:", consumeError)
        }
      }
    }

    // Start the consumer
    consumeMessages()

    // Cleanup function
    return () => {
      aborted = true
      // Properly close the message iterator to release resources
      messagesIterator?.close().catch((err) => {
        // Ignore errors during cleanup (e.g., connection already closed)
        if (!aborted) {
          console.error("Error closing message iterator:", err)
        }
      })
    }
  }, [consumer]) // Only re-run when consumer changes
}
