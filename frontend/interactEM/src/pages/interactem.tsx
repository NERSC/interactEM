import { ReactFlowProvider } from "@xyflow/react"
import ExternalAuthProvider from "../auth/externalprovider"
import InternalAuthProvider from "../auth/internalprovider"
import config from "../config"
import { DnDProvider } from "../hooks/useDnD"
import { NatsProvider } from "../nats/NatsContext"

import { QueryClientProvider } from "@tanstack/react-query"
import "@xyflow/react/dist/style.css"
import { Flip, ToastContainer } from "react-toastify"
import { interactemQueryClient } from "../auth/api"
import NotificationsToast from "../components/notificationstoast"
import { PipelineProvider } from "../hooks/usePipelineContext"
import "../index.css"
import ComposerPage from "./composerpage"

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
              <PipelineProvider>
                <ComposerPage />
              </PipelineProvider>
            </DnDProvider>
          </ReactFlowProvider>
          <ToastContainer
            position="top-center"
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
