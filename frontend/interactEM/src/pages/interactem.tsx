import { ReactFlowProvider } from "@xyflow/react"
import ExternalAuthProvider from "../auth/externalprovider"
import InternalAuthProvider from "../auth/internalprovider"
import config from "../config"
import { DnDProvider } from "../contexts/dnd"
import { NatsProvider } from "../contexts/nats"

import { QueryClientProvider } from "@tanstack/react-query"
import "@xyflow/react/dist/style.css"
import { Flip, ToastContainer } from "react-toastify"
import { interactemQueryClient } from "../auth/api"
import NotificationsToast from "../components/notificationstoast"
import { StatusProvider } from "../contexts/nats/allstatus"
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
          <StatusProvider>
            <NotificationsToast />
            <ReactFlowProvider>
              <DnDProvider>
                <ComposerPage />
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
          </StatusProvider>
        </NatsProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
