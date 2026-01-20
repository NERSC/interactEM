import { Chip, Tooltip } from "@mui/material"
import type { NatsConnection } from "@nats-io/nats-core"
import { useMemo } from "react"
import { useNats } from "../contexts/nats"

type NatsStatus = {
  color: "success" | "warning" | "error"
  label: string
  tooltip: string
}

export const NATS_STATUS_TOOLTIPS = {
  disconnected: "NATS is not connected",
  draining: "NATS connection is draining",
  closed: "NATS connection is closed",
  connected: "NATS connection is active",
  connecting: "NATS connection is establishing",
} as const

const getNatsStatus = (
  connection: NatsConnection | null,
  isConnected: boolean,
): NatsStatus => {
  if (!connection) {
    return {
      color: "error",
      label: "Disconnected",
      tooltip: NATS_STATUS_TOOLTIPS.disconnected,
    }
  }

  if (connection.isDraining()) {
    return {
      color: "warning",
      label: "Draining",
      tooltip: NATS_STATUS_TOOLTIPS.draining,
    }
  }

  if (connection.isClosed()) {
    return {
      color: "error",
      label: "Closed",
      tooltip: NATS_STATUS_TOOLTIPS.closed,
    }
  }

  if (isConnected) {
    return {
      color: "success",
      label: "Connected",
      tooltip: NATS_STATUS_TOOLTIPS.connected,
    }
  }

  return {
    color: "warning",
    label: "Connecting",
    tooltip: NATS_STATUS_TOOLTIPS.connecting,
  }
}

export const NatsStatusIndicator = () => {
  const { natsConnection, isConnected } = useNats()
  const status = useMemo(
    () => getNatsStatus(natsConnection, isConnected),
    [natsConnection, isConnected],
  )

  return (
    <Tooltip title={status.tooltip} arrow placement="top">
      <Chip label="NATS" color={status.color} size="small" variant="outlined" />
    </Tooltip>
  )
}
