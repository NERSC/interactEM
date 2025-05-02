import { useEffect, useState } from "react"
import { AGENTS_BUCKET } from "../constants/nats"
import { type Agent, AgentSchema } from "../types/agent"
import { useBucket } from "./useBucket"

const isValidAgent = (data: unknown): data is Agent => {
  const parseResult = AgentSchema.safeParse(data)
  if (!parseResult.success) {
    console.warn("Validation errors:", parseResult.error.issues)
  }
  return parseResult.success
}

export const useAgents = () => {
  const [agents, setAgents] = useState<Agent[]>([])
  const [error, setError] = useState<string | null>(null)
  const bucket = useBucket(AGENTS_BUCKET)

  useEffect(() => {
    if (!bucket) return

    const abortController = new AbortController()
    const signal = abortController.signal

    // Setup a watcher to receive updates for agent changes.
    ;(async () => {
      try {
        const watch = await bucket.watch()

        // Process the watch until the component unmounts
        const processWatch = async () => {
          try {
            for await (const entry of watch) {
              // Exit the loop if the component has unmounted
              if (signal.aborted) {
                watch.stop()
                return
              }

              const key = entry.key
              setAgents((prevAgents) => {
                // Remove any agent matching the given key (agent ID)
                const filteredAgents = prevAgents.filter(
                  (a) => a.uri.id !== key,
                )

                // Agent removal
                if (entry.operation === "DEL" || entry.operation === "PURGE") {
                  return filteredAgents
                }

                // If there's no value, skip updating.
                if (!entry.value) {
                  console.warn(`No value for key ${key}, skipping`)
                  return filteredAgents
                }

                // Parse and validate new/updated agent data.
                try {
                  const data = entry.json<Agent>()
                  if (isValidAgent(data)) {
                    // If agent already exists, update in place to preserve order
                    const existingIndex = prevAgents.findIndex(
                      (a) => a.uri.id === key,
                    )
                    if (existingIndex !== -1) {
                      // Replace the agent at the same index
                      const updatedAgents = [...prevAgents]
                      updatedAgents[existingIndex] = data
                      return updatedAgents
                    }
                    // New agent, add to end
                    return [...prevAgents, data]
                  }
                  console.warn(`Invalid agent data for key ${key}`, data)
                  return filteredAgents
                } catch (parseError) {
                  console.error(
                    `Failed to parse agent data for key ${key}:`,
                    parseError,
                  )
                  return filteredAgents
                }
              })
            }
          } catch (err) {
            if (!signal.aborted) {
              console.error("Watch error:", err)
              setError("Failed to watch agents")
            }
          }
        }

        processWatch()
      } catch (err) {
        if (!signal.aborted) {
          console.error("Error setting up watch:", err)
          setError("Failed to set up agent watch")
        }
      }
    })()

    // Cleanup when unmounting
    return () => {
      abortController.abort()
    }
  }, [bucket])

  return { agents, error }
}
