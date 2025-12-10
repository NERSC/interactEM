import type { KvEntry, KvWatchOptions } from "@nats-io/kv"
import {
  DrainingConnectionError,
  RequestError,
} from "@nats-io/nats-core/internal"
import { useEffect, useState } from "react"
import type { z } from "zod"
import { useBucket } from "./useBucket"

// We need to ensure that the type has an id property
// or a uri property with an id property
type WithId = { id: string } | { uri: { id: string } }

interface UseBucketWatchOptions<T extends WithId> {
  bucketName: string
  schema: z.ZodSchema<T>
  keyFilter?: string | string[]
  stripPrefix?: string
}

export function useBucketWatch<T extends WithId>({
  bucketName,
  schema,
  keyFilter,
  stripPrefix = "",
}: UseBucketWatchOptions<T>) {
  const [items, setItems] = useState<T[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const bucket = useBucket(bucketName)

  useEffect(() => {
    if (!bucket) return

    const abortController = new AbortController()
    const signal = abortController.signal

    // Validate data based on schema
    const validateAndParse = (entry: KvEntry): T | null => {
      if (!entry.value) return null

      try {
        const data = entry.json<any>()
        const parseResult = schema.safeParse(data)

        if (parseResult.success) {
          return parseResult.data
        }
        console.warn(
          `Validation error for key ${entry.key}:`,
          parseResult.error,
        )
        return null
      } catch (error) {
        console.error(`Failed to parse data for key ${entry.key}:`, error)
        return null
      }
    }

    // Watch for changes
    ;(async () => {
      try {
        const watchOptions: KvWatchOptions | undefined = keyFilter
          ? { key: keyFilter }
          : undefined

        const watch = await bucket.watch(watchOptions)

        const processWatch = async () => {
          for await (const entry of watch) {
            if (signal.aborted) {
              watch.stop()
              return
            }

            const key = entry.key
            // since we are using a subject prefix (e.g., "<prefix>.<id>")
            // we need to strip the prefix for filtering
            const strippedKey = stripPrefix
              ? key.replace(`${stripPrefix}.`, "")
              : key

            setItems((prevItems) => {
              // Simply filter based on id property
              const filteredItems = prevItems.filter((item) => {
                // Check both possible ID locations from the WithId type
                const itemId = "id" in item ? item.id : item.uri.id
                return itemId !== strippedKey
              })

              // Handle deletion
              if (entry.operation === "DEL" || entry.operation === "PURGE") {
                return filteredItems
              }

              // Skip if no value
              if (!entry.value) {
                return filteredItems
              }

              const item = validateAndParse(entry)
              if (item) {
                return [...filteredItems, item]
              }
              return filteredItems
            })

            // Mark loading as complete after initial entries have been processed
            if (isLoading && !signal.aborted) {
              setIsLoading(false)
            }
          }
        }

        processWatch()
      } catch (err) {
        if (signal.aborted) return
        if (
          err instanceof DrainingConnectionError ||
          err instanceof RequestError
        ) {
          // Ignore transient connection issues; hooks will re-run after reconnect
          return
        }
        console.error(`Watch error for bucket ${bucketName}:`, err)
        setError(`Failed to watch bucket ${bucketName}`)
        setIsLoading(false)
      }
    })()

    return () => {
      abortController.abort()
    }
  }, [bucket, stripPrefix, bucketName, schema, keyFilter, isLoading])

  return { items, error, isLoading }
}
