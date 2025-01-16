import { ReactFlowProvider } from "@xyflow/react"
import { DnDProvider } from "../dnd/dndcontext"
import "@xyflow/react/dist/style.css"
import "../index.css"
import { PipelineFlow } from "../components/pipelineflow"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { NatsProvider } from "../nats/NatsContext"
import "../client/setupClient"

const queryClient = new QueryClient()

export function InteractEM() {
  return (
    <NatsProvider>
      <QueryClientProvider client={queryClient}>
        <ReactFlowProvider>
          <DnDProvider>
            <PipelineFlow />
          </DnDProvider>
        </ReactFlowProvider>
        <ReactQueryDevtools />
      </QueryClientProvider>
    </NatsProvider>
  )
}
