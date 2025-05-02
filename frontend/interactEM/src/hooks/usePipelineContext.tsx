import { type ReactNode, createContext, useContext, useMemo } from "react"
import { usePipelineStore } from "../stores"
import { useRunningPipelines } from "./useRunningPipelines"

interface PipelineContextType {
  isCurrentPipelineRunning: boolean
}

const PipelineContext = createContext<PipelineContextType>({
  isCurrentPipelineRunning: false,
})

export const PipelineProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const { currentPipelineId } = usePipelineStore()
  const { pipelines } = useRunningPipelines()

  const isCurrentPipelineRunning = useMemo(
    () => pipelines.some((p) => p.id === currentPipelineId),
    [pipelines, currentPipelineId],
  )

  const contextValue = useMemo(
    () => ({
      isCurrentPipelineRunning,
    }),
    [isCurrentPipelineRunning],
  )

  return (
    <PipelineContext.Provider value={contextValue}>
      {children}
    </PipelineContext.Provider>
  )
}

export const usePipelineContext = () => useContext(PipelineContext)
