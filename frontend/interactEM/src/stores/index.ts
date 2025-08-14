import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { PipelinePublic, PipelineRevisionPublic } from "../client"

interface PipelineState {
  currentPipelineId: string | null
  setCurrentPipelineId: (id: string | null) => void
  currentRevisionId: number | null
  setCurrentRevisionId: (id: number | null) => void
  setPipelineAndRevision: (
    pipelineId: string | null,
    revisionId: number | null,
  ) => void
  selectedRuntimePipelineId: string | null
  setSelectedRuntimePipelineId: (id: string | null) => void
}

export enum ViewMode {
  Composer = "composer",
  Runtime = "runtime",
}

interface ViewModeState {
  viewMode: ViewMode
  setViewMode: (mode: ViewMode) => void
}

const usePipelineStoreZustand = create<PipelineState>()(
  persist(
    (set) => ({
      currentPipelineId: null,
      setCurrentPipelineId: (id) => set({ currentPipelineId: id }),
      currentRevisionId: null,
      setCurrentRevisionId: (id) => set({ currentRevisionId: id }),
      setPipelineAndRevision: (pipelineId, revisionId) =>
        set({ currentPipelineId: pipelineId, currentRevisionId: revisionId }),
      selectedRuntimePipelineId: null,
      setSelectedRuntimePipelineId: (id) =>
        set({ selectedRuntimePipelineId: id }),
    }),
    { name: "pipeline-storage" },
  ),
)

const useViewModeStoreZustand = create<ViewModeState>()(
  persist(
    (set) => ({
      viewMode: ViewMode.Composer,
      setViewMode: (mode) => set({ viewMode: mode }),
    }),
    { name: "view-mode-storage" },
  ),
)

export const usePipelineStore = () => {
  const currentPipelineId = usePipelineStoreZustand(
    (state) => state.currentPipelineId,
  )
  const setCurrentPipelineId = usePipelineStoreZustand(
    (state) => state.setCurrentPipelineId,
  )
  const currentRevisionId = usePipelineStoreZustand(
    (state) => state.currentRevisionId,
  )
  const setCurrentRevisionId = usePipelineStoreZustand(
    (state) => state.setCurrentRevisionId,
  )
  const setPipelineAndRevision = usePipelineStoreZustand(
    (state) => state.setPipelineAndRevision,
  )
  const selectedRuntimePipelineId = usePipelineStoreZustand(
    (state) => state.selectedRuntimePipelineId,
  )
  const setSelectedRuntimePipelineId = usePipelineStoreZustand(
    (state) => state.setSelectedRuntimePipelineId,
  )

  // Helper to set both IDs from a PipelineRevisionPublic object
  const setPipelineRevision = (data: PipelineRevisionPublic | null) => {
    if (data) {
      setPipelineAndRevision(data.pipeline_id, data.revision_id)
    } else {
      setPipelineAndRevision(null, null)
    }
  }

  // Helper to set both IDs from a PipelinePublic object
  const setPipeline = (data: PipelinePublic | null) => {
    if (data) {
      setPipelineAndRevision(data.id, data.current_revision_id)
    } else {
      setPipelineAndRevision(null, null)
    }
  }

  return {
    currentPipelineId,
    setCurrentPipelineId,
    currentRevisionId,
    setCurrentRevisionId,
    setPipelineAndRevision,
    setPipelineRevision,
    setPipeline,
    selectedRuntimePipelineId,
    setSelectedRuntimePipelineId,
  }
}

export const useViewModeStore = () => {
  const viewMode = useViewModeStoreZustand((state) => state.viewMode)
  const setViewMode = useViewModeStoreZustand((state) => state.setViewMode)

  return {
    viewMode,
    setViewMode,
  }
}
