import { type ReactNode, createContext, useContext, useMemo } from "react"
import { BUCKET_STATUS, OPERATORS } from "../../constants/nats"
import { useBucketWatch } from "../../hooks/nats/useBucketWatch"
import type { OperatorVal } from "../../types/gen"
import { OperatorValSchema } from "../../types/operator"

interface OperatorStatusContextType {
  operators: OperatorVal[]
  operatorsLoading: boolean
  operatorsError: string | null
}

const OperatorStatusContext = createContext<OperatorStatusContextType>({
  operators: [],
  operatorsLoading: true,
  operatorsError: null,
})

export const OperatorStatusProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const {
    items: operators,
    isLoading: operatorsLoading,
    error: operatorsError,
  } = useBucketWatch<OperatorVal>({
    bucketName: BUCKET_STATUS,
    schema: OperatorValSchema,
    keyFilter: `${OPERATORS}.>`,
    stripPrefix: OPERATORS,
  })

  const contextValue = useMemo(
    () => ({ operators, operatorsLoading, operatorsError }),
    [operators, operatorsLoading, operatorsError],
  )

  return (
    <OperatorStatusContext.Provider value={contextValue}>
      {children}
    </OperatorStatusContext.Provider>
  )
}

export const useOperatorStatusContext = () => useContext(OperatorStatusContext)
