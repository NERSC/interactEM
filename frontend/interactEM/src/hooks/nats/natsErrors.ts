import {
  ClosedConnectionError,
  DrainingConnectionError,
} from "@nats-io/nats-core"

export function isConnectionError(err: unknown): boolean {
  return (
    err instanceof DrainingConnectionError ||
    err instanceof ClosedConnectionError
  )
}
