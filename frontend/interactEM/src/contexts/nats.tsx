import {
  type JetStreamClient,
  type JetStreamManager,
  jetstream,
  jetstreamManager,
} from "@nats-io/jetstream"
import { Kvm } from "@nats-io/kv"
import {
  type NatsConnection,
  jwtAuthenticator,
  tokenAuthenticator,
  wsconnect,
} from "@nats-io/nats-core"
import type React from "react"
import { createContext, useContext, useEffect, useRef, useState } from "react"
import { useAuth } from "../auth/base"

type NatsContextType = {
  natsConnection: NatsConnection | null
  jetStreamClient: JetStreamClient | null
  jetStreamManager: JetStreamManager | null
  keyValueManager: Kvm | null
  isConnected: boolean
}

const NatsContext = createContext<NatsContextType>({
  natsConnection: null,
  jetStreamClient: null,
  jetStreamManager: null,
  keyValueManager: null,
  isConnected: false,
})

const getConnectionId = () => {
  let id = sessionStorage.getItem("interactEM-connection-id")
  if (!id) {
    id = `interactEM-${Date.now()}-${Math.random().toString(36).substring(2, 15)}`
    sessionStorage.setItem("interactEM-connection-id", id)
  }
  return id
}

export const useNats = (): NatsContextType => {
  const context = useContext(NatsContext)
  if (!context) {
    throw new Error("useNats must be used within a NatsProvider")
  }
  return context
}

export type NatsProviderProps = {
  children: React.ReactNode
  natsServers: string | string[]
}

export const NatsProvider: React.FC<NatsProviderProps> = ({
  children,
  natsServers,
}) => {
  const [state, setState] = useState<NatsContextType>({
    natsConnection: null,
    jetStreamClient: null,
    jetStreamManager: null,
    keyValueManager: null,
    isConnected: false,
  })

  const [natsConnection, setNatsConnection] = useState<NatsConnection | null>(
    null,
  )
  const { token, natsJwt, isAuthenticated } = useAuth()
  const tokenRef = useRef(token)
  const natsJwtRef = useRef(natsJwt)

  useEffect(() => {
    tokenRef.current = token
  }, [token])

  useEffect(() => {
    if (!isAuthenticated) {
      return
    }
    async function setupNatsServices(nc: NatsConnection) {
      try {
        const js = jetstream(nc)
        const jsm = await jetstreamManager(nc)
        const kvm = new Kvm(nc)

        setState({
          natsConnection: nc,
          jetStreamClient: js,
          jetStreamManager: jsm,
          keyValueManager: kvm,
          isConnected: true,
        })
      } catch (error) {
        console.error("Failed to setup NATS services:", error)
        setState((prev) => ({ ...prev, isConnected: false }))
      }
    }
    async function connect() {
      try {
        const servers = Array.isArray(natsServers) ? natsServers : [natsServers]
        const nc = await wsconnect({
          servers: servers,
          name: getConnectionId(),
          authenticator: [
            tokenAuthenticator(() => {
              const currentToken = tokenRef.current
              if (!currentToken) {
                throw new Error("No token available")
              }
              return currentToken
            }),
            jwtAuthenticator(() => {
              const currentJwt = natsJwtRef.current
              if (!currentJwt) {
                throw new Error("No JWT available")
              }
              return currentJwt
            }),
          ],
          reconnect: true,
          reconnectTimeWait: 1000,
          maxReconnectAttempts: 30,
        })

        console.log("NATS connection successful")

        setNatsConnection(nc)
        await setupNatsServices(nc)

        // natsConnection will cycle through the following status sequence when
        // it is disconnected:
        // 1. Error
        // 2. staleConnection
        // 3. disconnect
        // 4. reconnecting
        // 5. update
        // 6. reconnect
        ;(async () => {
          for await (const status of nc.status()) {
            console.log("NATS status change:", status.type, status)
            switch (status.type) {
              case "reconnect":
                setState((prev) => ({ ...prev, isConnected: true }))
                break
              case "error":
                // TODO: handle error better, maybe with UI update
                setState((prev) => ({
                  ...prev,
                  isConnected: false,
                }))
                break
            }
          }
        })().catch(console.error)
      } catch (error) {
        console.error("Failed to connect to NATS:", error)
        setState((prev) => ({ ...prev, isConnected: false }))
      }
    }

    if (!natsConnection) {
      connect()
    }
    return () => {
      if (natsConnection) {
        console.log("Draining NATS connection")
        ;(async () => {
          try {
            await natsConnection.drain()
            console.log("NATS connection drained and closed")
          } catch (err) {
            console.error("Error draining NATS connection:", err)
          }
        })()
      }
      setState({
        natsConnection: null,
        jetStreamClient: null,
        jetStreamManager: null,
        keyValueManager: null,
        isConnected: false,
      })
    }
  }, [isAuthenticated, natsConnection, natsServers])

  if (!isAuthenticated) {
    return null
  }

  return <NatsContext.Provider value={state}>{children}</NatsContext.Provider>
}
