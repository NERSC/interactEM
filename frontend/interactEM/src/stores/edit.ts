import { create } from "zustand"
import { persist } from "zustand/middleware"
import { usePipelineContext } from "../hooks/usePipelineContext"

interface EditModeState {
  isEditMode: boolean
  setIsEditMode: (isEditMode: boolean) => void
}

export const useEditModeStore = create<EditModeState>()(
  persist(
    (set) => ({
      isEditMode: false,
      setIsEditMode: (isEditMode) => set({ isEditMode }),
    }),
    {
      name: "edit-mode-storage",
    },
  ),
)

export const useEditModeState = () => {
  const { isCurrentPipelineRunning } = usePipelineContext()

  const isEditMode = useEditModeStore((state) => state.isEditMode)
  const setIsEditMode = useEditModeStore((state) => state.setIsEditMode)

  // If pipeline is running, edit mode should be disabled
  const canEdit = !isCurrentPipelineRunning

  // The actual edit mode state considering the running state
  const effectiveEditMode = canEdit && isEditMode

  return {
    isEditMode: effectiveEditMode,
    setIsEditMode,
    canEdit,
  }
}
