import { create } from "zustand"
import { persist } from "zustand/middleware"

interface PipelineState {
  currentPipelineId: string | null
  setCurrentPipelineId: (id: string | null) => void
}

export const usePipelineStore = create<PipelineState>()(
  persist(
    (set) => ({
      currentPipelineId: null,
      setCurrentPipelineId: (id) => set({ currentPipelineId: id }),
    }),
    {
      name: "pipeline-storage",
    },
  ),
)
