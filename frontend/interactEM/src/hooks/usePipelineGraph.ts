import type { Edge } from "@xyflow/react"
import { useEffect, useState } from "react"
import type { PipelineRevisionPublic } from "../client"
import { useViewModeStore } from "../stores"
import type { OperatorNodeTypes } from "../types/nodes"
import { applyPositionsToNodes, layoutNodes } from "../utils/layout"
import { fromPipelineJSON } from "../utils/pipeline"

export function usePipelineGraph(
  pipelineData: PipelineRevisionPublic | null | undefined,
  fitView: (opts?: { duration?: number; padding?: number }) => void,
) {
  const [nodes, setNodes] = useState<OperatorNodeTypes[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [pipelineJSONLoaded, setPipelineJSONLoaded] = useState(false)
  const { viewMode } = useViewModeStore()

  useEffect(() => {
    if (!pipelineData) {
      setNodes([])
      setEdges([])
      setPipelineJSONLoaded(false)
      return
    }

    const { nodes: importedNodes, edges: importedEdges } = fromPipelineJSON(
      pipelineData,
      viewMode,
    )

    // Use saved positions if available, otherwise apply dagre layout
    let finalNodes: OperatorNodeTypes[]
    let finalEdges: Edge[]

    if (pipelineData.positions.length > 0) {
      const result = applyPositionsToNodes(
        importedNodes,
        pipelineData.positions,
        importedEdges,
      )
      finalNodes = result.nodes as OperatorNodeTypes[]
      finalEdges = result.edges
    } else {
      const result = layoutNodes(importedNodes, importedEdges)
      finalNodes = result.nodes as OperatorNodeTypes[]
      finalEdges = result.edges
    }

    setNodes(finalNodes)
    setEdges(finalEdges)
    setPipelineJSONLoaded(true)

    const id = setTimeout(() => {
      fitView({ duration: 300, padding: 0.1 })
    }, 100)

    return () => clearTimeout(id)
  }, [pipelineData, viewMode, fitView])

  return {
    nodes,
    setNodes,
    edges,
    setEdges,
    pipelineJSONLoaded,
    setPipelineJSONLoaded,
  }
}
