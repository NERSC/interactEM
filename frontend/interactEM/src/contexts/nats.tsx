import {
  type JetStreamClient,
  type JetStreamManager,
  jetstream,
  jetstreamManager,
} from "@nats-io/jetstream"
import { Kvm } from "@nats-io/kv"
import {
  type NatsConnection,
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

  const { token, isAuthenticated } = useAuth()
  const tokenRef = useRef(token)
  const hasConnectedRef = useRef(false)
  const connectionRef = useRef<NatsConnection | null>(null)

  useEffect(() => {
    tokenRef.current = token
  }, [token])

  useEffect(() => {
    if (!isAuthenticated) {
      return
    }

    async function setupNatsServices(nc: NatsConnection): Promise<boolean> {
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
        return true
      } catch (error) {
        console.error("Failed to setup NATS services:", error)
        setState((prev) => ({ ...prev, isConnected: false }))
        return false
      }
    }

    async function connect() {
      try {
        const servers = Array.isArray(natsServers) ? natsServers : [natsServers]

        const nc = await wsconnect({
          servers: servers,
          name: getConnectionId(),
          authenticator: tokenAuthenticator(() => {
            const currentToken = tokenRef.current
            if (!currentToken) {
              throw new Error("No token available")
            }
            return currentToken
          }),
          reconnect: true,
          reconnectTimeWait: 1000,
          maxReconnectAttempts: 30,
        })

        connectionRef.current = nc
        console.log("NATS connection successful")

        const setupOk = await setupNatsServices(nc)
        if (!setupOk) {
          try {
            await nc.drain()
          } catch (err) {
            console.error("Error draining NATS connection:", err)
          }
          connectionRef.current = null
          hasConnectedRef.current = false
          return
        }
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
            switch (status.type) {
              case "reconnect":
                setState((prev) => ({ ...prev, isConnected: true }))
                break
              case "error":
              case "disconnect":
              case "staleConnection":
              case "close":
                setState((prev) => ({ ...prev, isConnected: false }))
                break
            }
          }
        })().catch(console.error)
      } catch (error) {
        console.error("Failed to connect to NATS:", error)
        setState((prev) => ({ ...prev, isConnected: false }))
        hasConnectedRef.current = false
        const nc = connectionRef.current
        connectionRef.current = null
        if (nc) {
          try {
            await nc.drain()
          } catch (err) {
            console.error("Error draining NATS connection:", err)
          }
        }
      }
    }

    if (!hasConnectedRef.current) {
      hasConnectedRef.current = true
      connect()
    }

    return () => {
      hasConnectedRef.current = false
      const nc = connectionRef.current
      connectionRef.current = null
      if (nc) {
        console.log("Draining NATS connection")
        ;(async () => {
          try {
            await nc.drain()
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
  }, [isAuthenticated, natsServers])

  if (!isAuthenticated) {
    return null
  }

  return <NatsContext.Provider value={state}>{children}</NatsContext.Provider>
}
