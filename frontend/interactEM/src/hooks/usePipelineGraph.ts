import type { Edge } from "@xyflow/react"
import { useEffect, useState } from "react"
import type { PipelineRevisionPublic } from "../client"
import { useViewModeStore } from "../stores"
import type { OperatorNodeTypes } from "../types/nodes"
import { layoutNodes } from "../utils/layout"
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

    const { nodes: layoutedNodes, edges: layoutedEdges } = layoutNodes(
      importedNodes,
      importedEdges,
    )

    setNodes(layoutedNodes as OperatorNodeTypes[])
    setEdges(layoutedEdges)
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
