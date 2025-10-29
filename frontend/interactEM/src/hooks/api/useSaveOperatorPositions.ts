import { useMutation, useQueryClient } from "@tanstack/react-query"
import { z } from "zod"
import type { OperatorPosition } from "../../client"
import {
  pipelinesReadPipelineQueryKey,
  pipelinesUpdatePipelineRevisionPositionsMutation,
} from "../../client/generated/@tanstack/react-query.gen"
import { zOperatorPosition } from "../../client/generated/zod.gen"
import { usePipelineStore } from "../../stores"
import type { OperatorNodeTypes } from "../../types/nodes"

// Validation schema for positions array
const positionsSchema = z.array(zOperatorPosition)

export const useSaveOperatorPositions = (
  pipelineId?: string | null,
  revisionId?: number | null,
) => {
  const queryClient = useQueryClient()
  const storeData = usePipelineStore()

  // Use provided IDs or fall back to store IDs (for Composer mode)
  const finalPipelineId = pipelineId ?? storeData.currentPipelineId
  const finalRevisionId = revisionId ?? storeData.currentRevisionId

  const mutation = useMutation({
    ...pipelinesUpdatePipelineRevisionPositionsMutation(),
    onSuccess: () => {
      // Invalidate the pipeline query to refetch with new positions
      if (finalPipelineId) {
        queryClient.invalidateQueries({
          queryKey: pipelinesReadPipelineQueryKey({
            path: { id: finalPipelineId },
          }),
        })
      }
    },
  })

  const savePositions = (nodes: OperatorNodeTypes[]) => {
    if (!finalPipelineId || finalRevisionId == null) return

    // Convert nodes to OperatorPosition format
    const positions: OperatorPosition[] = nodes.map((node) => ({
      canonical_operator_id: node.id,
      x: node.position.x,
      y: node.position.y,
    }))

    // Validate positions with zod schema
    const validationResult = positionsSchema.safeParse(positions)
    if (!validationResult.success) {
      console.error(
        "Position validation failed:",
        validationResult.error.errors,
      )
      return
    }

    mutation.mutate({
      path: {
        id: finalPipelineId,
        revision_id: finalRevisionId,
      },
      body: {
        positions: validationResult.data,
      },
    })
  }

  return { savePositions, ...mutation }
}
