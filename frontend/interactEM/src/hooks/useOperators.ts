import { useEffect, useState } from "react";
import { Operator } from "../operators";

import {
  readOperators,
  ReadOperatorsError,
  ReadOperatorsResponse,
} from "../client";

const useOperators = () => {
  const [operators, setOperators] = useState<Operator[] | null>(null);
  const [error, setError] = useState<ReadOperatorsError | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const response = await readOperators();
        if (response.data) {
          setOperators((response.data.data as Operator[]) ?? null);
        }
      } catch (err) {
        setError(err as ReadOperatorsError);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  return { operators, error, loading };
};

export default useOperators;
