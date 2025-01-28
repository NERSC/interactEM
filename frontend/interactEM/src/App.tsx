import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import InteractEM from "./pages/interactem"

const queryClient = new QueryClient()
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <InteractEM authMode="internal" />
    </QueryClientProvider>
  )
}
