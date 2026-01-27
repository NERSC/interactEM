import {
  createContext,
  type FC,
  type ReactNode,
  useContext,
  useState,
} from "react"

type DnDContextType<T> = [
  T | null,
  React.Dispatch<React.SetStateAction<T | null>> | null,
]

type DnDContextValue = DnDContextType<unknown>

export const DnDContext = createContext<DnDContextValue>([null, null])

interface DnDProviderProps {
  children: ReactNode
}

export const DnDProvider: FC<{ children: ReactNode }> = <T,>({
  children,
}: DnDProviderProps) => {
  const [value, setValue] = useState<T | null>(null)

  return (
    <DnDContext.Provider value={[value, setValue] as DnDContextValue}>
      {children}
    </DnDContext.Provider>
  )
}

export default DnDContext

export const useDnD = <T,>() => {
  return useContext(DnDContext) as DnDContextType<T>
}
