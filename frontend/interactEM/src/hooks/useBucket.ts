import { useState, useEffect, useRef } from "react"
import { useNats } from "../nats/NatsContext"
import type { KV } from "@nats-io/kv"

export const useBucket = (bucketName: string): KV | null => {
  const { keyValueManager } = useNats()
  const [bucket, setBucket] = useState<KV | null>(null)
  const isMounted = useRef(true)

  useEffect(() => {
    isMounted.current = true

    const openBucket = async () => {
      if (keyValueManager && !bucket) {
        try {
          const openedBucket = await keyValueManager.open(bucketName)
          if (isMounted.current) {
            setBucket(openedBucket)
          }
        } catch (error) {
          console.error(`Failed to open bucket "${bucketName}":`, error)
        }
      }
    }

    openBucket()

    return () => {
      isMounted.current = false
    }
  }, [keyValueManager, bucket, bucketName])

  return bucket
}