import { Chip, Tooltip } from "@mui/material"
import type { NatsConnection } from "@nats-io/nats-core"
import { useMemo } from "react"
import { useNats } from "../contexts/nats"

type NatsStatus = {
  color: "success" | "warning" | "error"
  label: string
  tooltip: string
}

const getNatsStatus = (
  connection: NatsConnection | null,
  isConnected: boolean,
): NatsStatus => {
  if (!connection) {
    return {
      color: "error",
      label: "Disconnected",
      tooltip: "NATS is not connected",
    }
  }

  if (connection.isDraining()) {
    return {
      color: "warning",
      label: "Draining",
      tooltip: "NATS connection is draining",
    }
  }

  if (connection.isClosed()) {
    return {
      color: "error",
      label: "Closed",
      tooltip: "NATS connection is closed",
    }
  }

  if (isConnected) {
    return {
      color: "success",
      label: "Connected",
      tooltip: "NATS connection is active",
    }
  }

  return {
    color: "warning",
    label: "Connecting",
    tooltip: "NATS connection is establishing",
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
