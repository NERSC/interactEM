import { type ReactNode, createContext, useContext, useMemo } from "react"
import { BUCKET_STATUS, PIPELINES } from "../../constants/nats"
import { useBucketWatch } from "../../hooks/nats/useBucketWatch"
import type { PipelineRunVal } from "../../types/gen"
import { PipelineRunValSchema } from "../../types/pipeline"

interface PipelineStatusContextType {
  pipelines: PipelineRunVal[]
  pipelinesLoading: boolean
  pipelinesError: string | null
}

const PipelineStatusContext = createContext<PipelineStatusContextType>({
  pipelines: [],
  pipelinesLoading: true,
  pipelinesError: null,
})

export const PipelineStatusProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const {
    items: pipelines,
    isLoading: pipelinesLoading,
    error: pipelinesError,
  } = useBucketWatch<PipelineRunVal>({
    bucketName: BUCKET_STATUS,
    schema: PipelineRunValSchema,
    keyFilter: `${PIPELINES}.>`,
    stripPrefix: PIPELINES,
  })

  const contextValue = useMemo(
    () => ({ pipelines, pipelinesLoading, pipelinesError }),
    [pipelines, pipelinesLoading, pipelinesError],
  )

  return (
    <PipelineStatusContext.Provider value={contextValue}>
      {children}
    </PipelineStatusContext.Provider>
  )
}

export const usePipelineStatusContext = () => useContext(PipelineStatusContext)
