import { ReactFlowProvider } from "@xyflow/react"
import { DnDProvider } from "./dnd/dndcontext"

import "@xyflow/react/dist/style.css"
import { PipelineFlow } from "./components/pipelineflow"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ReactFlowProvider>
        <DnDProvider>
          <PipelineFlow />
        </DnDProvider>
      </ReactFlowProvider>
      <ReactQueryDevtools />
    </QueryClientProvider>
  )
}
