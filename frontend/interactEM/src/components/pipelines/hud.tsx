import type React from "react"
import { useViewModeStore, ViewMode } from "../../stores"
import { HudComposer } from "./hudcomposer"
import { HudRunning } from "./hudrunning"

export const PipelineHud: React.FC = () => {
  const { viewMode } = useViewModeStore()

  return viewMode === ViewMode.Composer ? <HudComposer /> : <HudRunning />
}
