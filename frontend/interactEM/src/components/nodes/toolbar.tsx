import DescriptionIcon from "@mui/icons-material/Description"
import InfoIcon from "@mui/icons-material/Info"
import RestartAltIcon from "@mui/icons-material/RestartAlt"
import { IconButton, Tooltip } from "@mui/material"
import { useMutation } from "@tanstack/react-query"
import { useNodesData } from "@xyflow/react"
import type React from "react"
import { useState } from "react"
import { toast } from "react-toastify"
import {
  type OperatorSpecParameter,
  type OperatorSpecTag,
  deploymentsCreateOperatorEventMutation,
} from "../../client"
import { useOperatorStatusContext } from "../../contexts/nats/operatorstatus"
import { ViewMode, usePipelineStore, useViewModeStore } from "../../stores"
import { OperatorStatus } from "../../types/gen"

import type { OperatorNodeType } from "../../types/nodes"
import OperatorLogsDialog from "../logs/operatordialog"
import ParametersButton from "./parametersbutton"

interface OperatorToolbarProps {
  id: string
  image: string
  parameters?: OperatorSpecParameter[] | null
  nodeRef: React.RefObject<HTMLDivElement>
}

const OperatorToolbar: React.FC<OperatorToolbarProps> = ({
  id,
  image,
  parameters,
  nodeRef,
}) => {
  const nodeData = useNodesData<OperatorNodeType>(id)
  const nodeTags = nodeData?.data.tags || []
  const { viewMode } = useViewModeStore()
  const { selectedRuntimePipelineId } = usePipelineStore()
  const { operators } = useOperatorStatusContext()
  const [logsDialogOpen, setLogsDialogOpen] = useState(false)

  // Find the operator status for this operator in the selected deployment
  const operatorStatus = operators.find(
    (op) =>
      op.canonical_id === id &&
      op.runtime_pipeline_id === selectedRuntimePipelineId,
  )?.status

  const isOperatorRunning = operatorStatus === OperatorStatus.running

  const restartOperatorMutation = useMutation({
    ...deploymentsCreateOperatorEventMutation(),
    onSuccess: () => {
      toast.success("Operator restart requested")
    },
    onError: () => {
      toast.error("Failed to request operator restart")
    },
  })

  const handleRestart = () => {
    if (!selectedRuntimePipelineId) {
      toast.error("Select a deployment to restart this operator")
      return
    }

    restartOperatorMutation.mutate({
      path: { id: selectedRuntimePipelineId, canonical_operator_id: id },
      body: { type: "operator_restart" },
    })
  }

  return (
    <div className="operator-toolbar">
      <div className="operator-icons">
        {viewMode === ViewMode.Runtime && isOperatorRunning && (
          <Tooltip title="Restart Operator" placement="top">
            <IconButton
              size="small"
              aria-label="Restart Operator"
              onClick={handleRestart}
              disabled={
                restartOperatorMutation.isPending || !selectedRuntimePipelineId
              }
            >
              <RestartAltIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}

        {parameters && parameters.length > 0 && (
          <ParametersButton
            operatorID={id}
            parameters={parameters}
            nodeRef={nodeRef}
          />
        )}

        {viewMode === ViewMode.Runtime && (
          <>
            <Tooltip title="View Logs" placement="top">
              <IconButton
                size="small"
                aria-label="Logs"
                onClick={() => setLogsDialogOpen(true)}
              >
                <DescriptionIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {logsDialogOpen && (
              <OperatorLogsDialog
                open={logsDialogOpen}
                onClose={() => setLogsDialogOpen(false)}
                canonicalOperatorId={id}
                operatorLabel={nodeData?.data.label || "Unknown"}
              />
            )}
          </>
        )}

        <Tooltip
          title={
            <div>
              <div>Image: {image}</div>
              {nodeTags.length > 0 && (
                <div>
                  Tags:
                  <ul style={{ margin: "5px 0", paddingLeft: "20px" }}>
                    {nodeTags.map((tag: OperatorSpecTag, index: number) => (
                      <li key={index}>
                        {tag.value}
                        {tag.description && (
                          <div>
                            <em>{tag.description}</em>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          }
          placement="top"
        >
          <IconButton size="small" aria-label="Info">
            <InfoIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </div>
    </div>
  )
}

export default OperatorToolbar
