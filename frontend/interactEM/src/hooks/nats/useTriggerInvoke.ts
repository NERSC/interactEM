import { useMutation } from "@tanstack/react-query"
import {
  NATS_TIMEOUT_DEFAULT,
  SUBJECT_OPERATORS_TRIGGERS,
} from "../../constants/nats"
import { useNats } from "../../contexts/nats"
import type { OperatorSpecTrigger } from "../../types/triggers"
import {
  TriggerInvocationRequestSchema,
  TriggerInvocationResponseSchema,
} from "../../types/triggers"

type InvokeArgs = {
  trigger: OperatorSpecTrigger
}

export const useTriggerInvoke = (operatorID: string) => {
  const { natsConnection } = useNats()

  const invokeTrigger = async ({ trigger }: InvokeArgs) => {
    if (!natsConnection) {
      throw new Error("No NATS connection available")
    }

    const reqBody = TriggerInvocationRequestSchema.parse({
      trigger: trigger.name,
    })

    const encoder = new TextEncoder()
    const decoder = new TextDecoder()
    const subject = `${SUBJECT_OPERATORS_TRIGGERS}.${operatorID}.${trigger.name}`
    const msg = await natsConnection.request(
      subject,
      encoder.encode(JSON.stringify(reqBody)),
      { timeout: NATS_TIMEOUT_DEFAULT * 1000 },
    )

    const parsed = JSON.parse(decoder.decode(msg.data))
    const resp = TriggerInvocationResponseSchema.parse(parsed)
    if (resp.status === "error") {
      throw new Error(resp.message || "Trigger rejected")
    }
    return resp
  }

  return useMutation({ mutationFn: invokeTrigger })
}
