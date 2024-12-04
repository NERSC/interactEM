import type React from "react"
import { createContext, useContext, useEffect, useState, useRef } from "react"
import { type NatsConnection, wsconnect } from "@nats-io/nats-core"
import {
  jetstream,
  type JetStreamClient,
  jetstreamManager,
  type JetStreamManager,
} from "@nats-io/jetstream"
import { Kvm } from "@nats-io/kv"
import config from "../config"

interface NatsContextType {
  natsConnection: NatsConnection | null
  jetStreamClient: JetStreamClient | null
  jetStreamManager: JetStreamManager | null
  keyValueManager: Kvm | null
  isConnected: boolean
}

const NatsContext = createContext<NatsContextType | undefined>(undefined)

export const useNats = (): NatsContextType => {
  const context = useContext(NatsContext)
  if (!context) {
    throw new Error("useNats must be used within a NatsProvider")
  }
  return context
}

export const NatsProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [natsConnection, setNatsConnection] = useState<NatsConnection | null>(
    null,
  )
  const [jetStreamClient, setJetStreamClient] =
    useState<JetStreamClient | null>(null)
  const [jetStreamManager, setJetStreamManager] =
    useState<JetStreamManager | null>(null)
  const [keyValueManager, setKeyValueManager] = useState<Kvm | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const isInitialized = useRef(false)

  useEffect(() => {
    const setupNatsConnection = async () => {
      try {
        const nc = await wsconnect({ servers: [config.NATS_SERVER_URL] })
        setNatsConnection(nc)
        setIsConnected(true)

        const js = jetstream(nc)
        setJetStreamClient(js)

        const jsm = await jetstreamManager(nc)
        setJetStreamManager(jsm)

        const kvm = new Kvm(nc)
        setKeyValueManager(kvm)
      } catch (error) {
        console.error("Failed to connect to NATS:", error)
        setIsConnected(false)
      }
    }

    if (!isInitialized.current) {
      setupNatsConnection()
      isInitialized.current = true
    }

    return () => {
      if (natsConnection) {
        natsConnection.close()
      }
    }
  }, [natsConnection])

  return (
    <NatsContext.Provider
      value={{
        natsConnection,
        jetStreamClient,
        jetStreamManager,
        keyValueManager,
        isConnected,
      }}
    >
      {children}
    </NatsContext.Provider>
  )
}
