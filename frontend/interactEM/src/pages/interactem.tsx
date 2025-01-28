import { ReactFlowProvider } from "@xyflow/react"
import ExternalAuthProvider from "../auth/externalprovider"
import InternalAuthProvider from "../auth/internalprovider"
import { PipelineFlow } from "../components/pipelineflow"
import config from "../config"
import { DnDProvider } from "../dnd/dndcontext"
import { useQueryClientContext } from "../hooks/useQueryClientContext"
import { NatsProvider } from "../nats/NatsContext"

import "../index.css"
import "@xyflow/react/dist/style.css"

interface InteractEMProps {
  authMode?: "external" | "internal"
  apiBaseURL?: string
  natsServers?: string | string[]
}

export default function InteractEM({
  authMode = "external",
  apiBaseURL = config.API_BASE_URL,
  natsServers = config.NATS_SERVER_URL,
}: InteractEMProps = {}) {
  // Check if we can successfully use the query client
  useQueryClientContext()

  const AuthProvider =
    authMode === "external" ? ExternalAuthProvider : InternalAuthProvider

  return (
    <AuthProvider apiBaseUrl={apiBaseURL}>
      <NatsProvider natsServers={natsServers}>
        <ReactFlowProvider>
          <DnDProvider>
            <PipelineFlow />
          </DnDProvider>
        </ReactFlowProvider>
      </NatsProvider>
    </AuthProvider>
  )
}
