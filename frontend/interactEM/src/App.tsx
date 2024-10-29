import { ReactFlowProvider } from "@xyflow/react"
import { DnDProvider } from "./dnd/dndcontext"

import "@xyflow/react/dist/style.css"
import { PipelineFlow } from "./components/PipelineFlow"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { NatsProvider } from "./nats/NatsContext"

import "./client/setupClient"

const queryClient = new QueryClient()

export default function App() {
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
