import {
  AckPolicy,
  DeliverPolicy,
  type JsMsg,
  ReplayPolicy,
} from "@nats-io/jetstream"
import { useCallback, useMemo } from "react"
import { type TypeOptions, toast } from "react-toastify"
import {
  STREAM_NOTIFICATIONS,
  SUBJECT_NOTIFICATIONS_ERRORS,
} from "../constants/nats"
import { useConsumeMessages } from "../hooks/nats/useConsumeMessages"
import { useConsumer } from "../hooks/nats/useConsumer"

export default function NotificationsToast() {
  const config = useMemo(
    () => ({
      filter_subjects: [`${STREAM_NOTIFICATIONS}.>`],
      ack_policy: AckPolicy.All,
      deliver_policy: DeliverPolicy.New,
      replay_policy: ReplayPolicy.Instant,
    }),
    [],
  )
  const consumer = useConsumer({
    stream: `${STREAM_NOTIFICATIONS}`,
    config: config,
  })

  const handleMessage = useCallback(async (m: JsMsg) => {
    let toastType: TypeOptions = "info"

    if (m.subject === `${SUBJECT_NOTIFICATIONS_ERRORS}`) {
      toastType = "error"
    }

    const notification = m.string()
    toast(notification, { type: toastType })
  }, [])

  useConsumeMessages({ consumer, handleMessage })

  return null
}
