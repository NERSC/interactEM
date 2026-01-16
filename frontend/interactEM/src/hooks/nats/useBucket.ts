import type { KV } from "@nats-io/kv"
import { useEffect, useRef, useState } from "react"
import { useNats } from "../../contexts/nats"
import { isConnectionError } from "./natsErrors"

export const useBucket = (bucketName: string): KV | null => {
  const { keyValueManager, isConnected } = useNats()
  const [bucket, setBucket] = useState<KV | null>(null)
  const isMountedRef = useRef(true)

  useEffect(() => {
    isMountedRef.current = true
    // Create abort signal for this effect instance to handle race conditions
    // when connection drops mid-open and reconnects before promise settles
    const abortController = new AbortController()

    const openBucket = async () => {
      if (!keyValueManager || !isConnected) {
        return
      }

      try {
        const openedBucket = await keyValueManager.open(bucketName)

        // Check if this effect instance was aborted before setting state
        if (abortController.signal.aborted) {
          return
        }

        if (isMountedRef.current) {
          setBucket(openedBucket)
        }
      } catch (error) {
        // Check if this effect instance was aborted before handling error
        if (abortController.signal.aborted) {
          return
        }

        if (isConnectionError(error)) {
          // Silently ignore connection lifecycle errors
          return
        }
        console.error(`Failed to open bucket "${bucketName}":`, error)
      }
    }

    openBucket()

    return () => {
      isMountedRef.current = false
      abortController.abort()
      setBucket(null)
    }
  }, [keyValueManager, bucketName, isConnected])

  return bucket
}
