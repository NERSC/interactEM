import { ReactFlowProvider } from "@xyflow/react"
import ExternalAuthProvider from "../auth/externalprovider"
import InternalAuthProvider from "../auth/internalprovider"
import { client } from "../client"
import { PipelineFlow } from "../components/pipelineflow"
import clientConfig from "../config"
import { DnDProvider } from "../dnd/dndcontext"
import { useQueryClientContext } from "../hooks/useQueryClientContext"
import { NatsProvider } from "../nats/NatsContext"

import "../index.css"
import "@xyflow/react/dist/style.css"

client.setConfig({
  baseURL: clientConfig.API_BASE_URL,
})

interface InteractEMProps {
  authMode?: "external" | "internal"
}

export default function InteractEM({
  authMode = "external",
}: InteractEMProps = {}) {
  // Check if we can successfully use the query client
  useQueryClientContext()

  const AuthProvider =
    authMode === "external" ? ExternalAuthProvider : InternalAuthProvider

  return (
    <AuthProvider>
      <NatsProvider>
        <ReactFlowProvider>
          <DnDProvider>
            <PipelineFlow />
          </DnDProvider>
        </ReactFlowProvider>
      </NatsProvider>
    </AuthProvider>
  )
}
