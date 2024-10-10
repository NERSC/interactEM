import { ReactFlowProvider } from "@xyflow/react"
import { DnDProvider } from "./dnd/dndcontext"

import "@xyflow/react/dist/style.css"
import { PipelineFlow } from "./components/pipelineflow"

export default function App() {
  return (
    <ReactFlowProvider>
      <DnDProvider>
        <PipelineFlow />
      </DnDProvider>
    </ReactFlowProvider>
  )
}
