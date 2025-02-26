import { ReactFlowProvider } from "@xyflow/react"
import ExternalAuthProvider from "../auth/externalprovider"
import InternalAuthProvider from "../auth/internalprovider"
import { PipelineFlow } from "../components/pipelineflow"
import config from "../config"
import { DnDProvider } from "../dnd/dndcontext"
import { NatsProvider } from "../nats/NatsContext"

import "../index.css"
import "@xyflow/react/dist/style.css"
import { QueryClientProvider } from "@tanstack/react-query"
import { Flip, ToastContainer } from "react-toastify"
import { interactemQueryClient } from "../auth/api"
import NotificationsToast from "../components/notificationstoast"

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
  const AuthProvider =
    authMode === "external" ? ExternalAuthProvider : InternalAuthProvider

  return (
    <QueryClientProvider client={interactemQueryClient}>
      <AuthProvider apiBaseUrl={apiBaseURL}>
        <NatsProvider natsServers={natsServers}>
          <NotificationsToast />
          <ReactFlowProvider>
            <DnDProvider>
              <PipelineFlow />
            </DnDProvider>
          </ReactFlowProvider>
          <ToastContainer
            position="top-left"
            autoClose={5000}
            hideProgressBar={false}
            newestOnTop
            closeOnClick
            pauseOnFocusLoss
            draggable
            pauseOnHover
            transition={Flip}
          />
        </NatsProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
