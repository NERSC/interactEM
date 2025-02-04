import {
  AckPolicy,
  DeliverPolicy,
  type JsMsg,
  ReplayPolicy,
} from "@nats-io/jetstream"
import { useCallback, useMemo } from "react"
import { type TypeOptions, toast } from "react-toastify"
import {
  NOTIFICATIONS_ERRORS_SUBJECT,
  NOTIFICATIONS_STREAM,
} from "../constants/nats"
import { useConsumeMessages } from "../hooks/useConsumeMessages"
import { useConsumer } from "../hooks/useConsumer"

export default function NotificationsToast() {
  const config = useMemo(
    () => ({
      filter_subjects: [`${NOTIFICATIONS_STREAM}.*`],
      ack_policy: AckPolicy.All,
      deliver_policy: DeliverPolicy.New,
      replay_policy: ReplayPolicy.Instant,
    }),
    [],
  )
  const consumer = useConsumer({
    stream: "notifications",
    config: config,
  })

  const handleMessage = useCallback(async (m: JsMsg) => {
    let toastType: TypeOptions = "info"

    if (m.subject === `${NOTIFICATIONS_ERRORS_SUBJECT}`) {
      toastType = "error"
    }

    const notification = m.string()
    toast(notification, { type: toastType })
  }, [])

  useConsumeMessages({ consumer, handleMessage })

  return null
}
