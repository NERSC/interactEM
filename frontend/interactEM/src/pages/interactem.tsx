import { ReactFlowProvider } from "@xyflow/react"
import { DnDProvider } from "../dnd/dndcontext"
import { PipelineFlow } from "../components/pipelineflow"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { NatsProvider } from "../nats/NatsContext"
import { client } from "../client"
import clientConfig from "../config"


import "../index.css"
import "@xyflow/react/dist/style.css"

client.setConfig({
  baseURL: clientConfig.API_BASE_URL,
})

const queryClient = new QueryClient()

export default function InteractEM() {
  return (
    <NatsProvider>
      <QueryClientProvider client={queryClient}>
        <ReactFlowProvider>
          <DnDProvider>
            <PipelineFlow />
          </DnDProvider>
        </ReactFlowProvider>
      </QueryClientProvider>
    </NatsProvider>
  )
}
