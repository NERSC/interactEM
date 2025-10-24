import type { NodeChange } from "@xyflow/react"
import { useCallback, useEffect, useRef } from "react"
import type { OperatorNodeTypes } from "../types/nodes"
import { useSaveOperatorPositions } from "./api/useSaveOperatorPositions"

const DEBOUNCE_TIME_MS = 500

/**
 * Hook to manage operator position tracking and persistence.
 * Provides debounced position saving across node changes.
 * @param nodes - The current pipeline nodes
 * @param pipelineId - Optional pipeline ID (if not provided, uses store value)
 * @param revisionId - Optional revision ID (if not provided, uses store value)
 */
export function usePositionTracking(
  nodes: OperatorNodeTypes[],
  pipelineId?: string | null,
  revisionId?: number | null,
) {
  const { savePositions } = useSaveOperatorPositions(pipelineId, revisionId)
  const positionSaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  )
  const previousPositionsRef = useRef<Map<
    string,
    { x: number; y: number }
  > | null>(null)

  // Initialize previous positions when nodes change
  useEffect(() => {
    previousPositionsRef.current = new Map(
      nodes.map((node) => [
        node.id,
        { x: node.position.x, y: node.position.y },
      ]),
    )
  }, [nodes])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (positionSaveTimeoutRef.current) {
        clearTimeout(positionSaveTimeoutRef.current)
      }
    }
  }, [])

  // Handle position changes with debounced saving.
  const handlePositionChanges = useCallback(
    (changes: NodeChange[], nextNodes: OperatorNodeTypes[]) => {
      const positionChanged = changes.some(
        (change) =>
          change.type === "position" &&
          change.position &&
          previousPositionsRef.current &&
          previousPositionsRef.current.get((change as { id: string }).id),
      )

      if (!positionChanged) return

      // Clear existing timeout
      if (positionSaveTimeoutRef.current) {
        clearTimeout(positionSaveTimeoutRef.current)
      }

      // Set new timeout to save positions after debounce period
      positionSaveTimeoutRef.current = setTimeout(() => {
        savePositions(nextNodes)
        previousPositionsRef.current = new Map(
          nextNodes.map((node) => [
            node.id,
            { x: node.position.x, y: node.position.y },
          ]),
        )
      }, DEBOUNCE_TIME_MS)
    },
    [savePositions],
  )

  return { handlePositionChanges }
}
