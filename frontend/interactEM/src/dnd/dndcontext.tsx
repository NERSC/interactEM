import {
  type FC,
  type ReactNode,
  createContext,
  useContext,
  useState,
} from "react"

type DnDContextType<T> = [
  T | null,
  React.Dispatch<React.SetStateAction<T | null>> | null,
]

export const DnDContext = createContext<
  [any | null, React.Dispatch<React.SetStateAction<any | null>> | null]
>([null, null])

interface DnDProviderProps {
  children: ReactNode
}

export const DnDProvider: FC<{ children: ReactNode }> = <T,>({
  children,
}: DnDProviderProps) => {
  const [value, setValue] = useState<T | null>(null)

  return (
    <DnDContext.Provider value={[value, setValue] as DnDContextType<T>}>
      {children}
    </DnDContext.Provider>
  )
}

export default DnDContext

export const useDnD = <T,>() => {
  return useContext(DnDContext) as DnDContextType<T>
}
