import { useQuery } from "@tanstack/react-query"
import { useNats } from "../nats/NatsContext"
import type { OperatorParameter } from "../operators"
import { useBucket } from "./useBucket"
import { useRef } from "react"
import { PARAMETERS_BUCKET, PARAMETERS_QUERYKEY } from "../constants/nats"

type OperatorParams = {
  [paramName: string]: string
}

export const useParameterValue = (
  operatorID: string,
  parameter: OperatorParameter,
): string => {
  const { jc } = useNats()
  const parametersBucket = useBucket(PARAMETERS_BUCKET)

  const previousData = useRef<string>(parameter.default)
  const dataChangedAtRef = useRef<number>(Date.now())

  const fetchParameterValue = async () => {
    if (parametersBucket) {
      const entry = await parametersBucket.get(operatorID)
      if (!entry) {
        return parameter.default
      }
      const v = jc.decode(entry.value) as OperatorParams
      if (parameter.name in v) {
        const fetchedValue = v[parameter.name]
        if (fetchedValue === previousData.current) {
          return previousData.current
        }
        previousData.current = fetchedValue
        dataChangedAtRef.current = Date.now()
        return fetchedValue
      }
    }
    return parameter.default
  }

  // Backoff interval for refetching the data.
  // We want to refetch more frequently after a mutation.
  // If a mutation hasn't happened, then we back off to avoid
  // uneccessary network.
  const refetchInterval = () => {
    const now = Date.now()
    const timeSinceLastChange = now - dataChangedAtRef.current

    const minInterval = 1000
    const maxInterval = 30000
    const backoffDuration = 60000

    const t = Math.min(timeSinceLastChange / backoffDuration, 1)
    const interval = minInterval + t * (maxInterval - minInterval)

    return interval
  }

  const { status, data: actualValue } = useQuery({
    queryKey: [PARAMETERS_QUERYKEY, operatorID, parameter.name],
    queryFn: fetchParameterValue,
    enabled: parametersBucket != null,
    initialData: parameter.default,
    refetchInterval: refetchInterval,
    refetchIntervalInBackground: true,
  })

  // Reset data change timestamp when the data is fetched
  // by query invalidation
  if (status === "success") {
    dataChangedAtRef.current = Date.now()
  }

  return actualValue
}
