import { useEffect, useRef } from "react"
import type { JsMsg, Consumer } from "@nats-io/jetstream"

interface UseConsumeMessagesOptions {
  consumer: Consumer | null
  handleMessage: (msg: JsMsg) => Promise<void> | void
}

export const useConsumeMessages = ({
  consumer,
  handleMessage,
}: UseConsumeMessagesOptions) => {
  // store a ref to the handleMessage function
  // instead of including it in the dependency array
  // This way we dont have to worry about re-rendering
  // and getting errors about consumer doing concurrent
  // consumes.

  // We should be able to pass in memoized or non-memoized
  // functions and it should be fine...

  // I pass in callbacks be safe

  const handleMessageRef = useRef(handleMessage)
  useEffect(() => {
    handleMessageRef.current = handleMessage
  }, [handleMessage])

  useEffect(() => {
    if (!consumer) return

    let isCancelled = false

    const consumeMessages = async () => {
      try {
        const messages = await consumer.consume()
        for await (const m of messages) {
          if (isCancelled) break
          await handleMessageRef.current(m)
          m.ack()
        }
      } catch (error) {
        console.error("Error consuming messages:", error)
      }
    }

    consumeMessages()

    return () => {
      isCancelled = true
    }
  }, [consumer])
}
