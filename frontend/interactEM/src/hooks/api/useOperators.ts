import { useEffect, useState } from "react"
import type { Operator } from "../../client"
import { operatorsReadOperators } from "../../client"

const useOperators = () => {
  const [operators, setOperators] = useState<Operator[] | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [loading, setLoading] = useState<boolean>(false)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const response = await operatorsReadOperators()
        if (response.data) {
          setOperators((response.data.data as Operator[]) ?? null)
        }
      } catch (err) {
        setError(err as Error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  return { operators, error, loading }
}

export default useOperators
