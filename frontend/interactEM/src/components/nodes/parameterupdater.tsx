import { Box, Button, Stack } from "@mui/material"
import { useReactFlow } from "@xyflow/react"
import { memo, useEffect, useState } from "react"
import type { OperatorSpecParameter } from "../../client"
import { useSavePipelineRevision } from "../../hooks/api/useSavePipelineRevision"
import { useOperatorInSelectedPipeline } from "../../hooks/nats/useOperatorStatus"
import { useParameterUpdate } from "../../hooks/nats/useParameterUpdate"
import { useParameterAck } from "../../hooks/nats/useParameterValue"
import { ViewMode, usePipelineStore, useViewModeStore } from "../../stores"
import type { OperatorNodeType } from "../../types/nodes"
import {
  getParameterInputSchema,
  getParameterNativeValue,
} from "../../types/params"
import NodeFieldInput, { type NodeFieldType } from "./nodefieldinput"
import ParameterInfoTooltip from "./parameterinfotooltip"

const ParameterUpdater: React.FC<{
  parameter: OperatorSpecParameter
  operatorCanonicalID: string
}> = ({ parameter, operatorCanonicalID }) => {
  const { viewMode } = useViewModeStore()
  const { selectedRuntimePipelineId } = usePipelineStore()
  const { isInRunningPipeline } =
    useOperatorInSelectedPipeline(operatorCanonicalID)
  const { setNodes, getNodes, getEdges } = useReactFlow<OperatorNodeType>()
  const { saveRevision } = useSavePipelineRevision()
  const { mutateAsync: updateParameter } = useParameterUpdate(
    operatorCanonicalID,
    parameter,
  )

  const { actualValue, hasReceivedMessage } = useParameterAck(
    operatorCanonicalID,
    parameter.name,
    String(parameter.default),
  )

  const hasRuntimePipeline = !!selectedRuntimePipelineId && isInRunningPipeline
  const isRuntimeMode = viewMode === ViewMode.Runtime && hasRuntimePipeline

  const currentValue = isRuntimeMode
    ? hasReceivedMessage
      ? actualValue
      : parameter.default
    : parameter.default

  const displayValue = String(currentValue)
  const isReadOnly = viewMode === ViewMode.Runtime && !hasRuntimePipeline

  const [inputValue, setInputValue] = useState(displayValue)
  const [error, setError] = useState<string | null>(null)
  const [userEditing, setUserEditing] = useState(false)

  useEffect(() => {
    if (!userEditing || isReadOnly) {
      setInputValue(displayValue)
    }
    if (isReadOnly) setUserEditing(false)
  }, [displayValue, isReadOnly, userEditing])

  const handleValueChange = (val: string) => {
    if (isReadOnly) return
    setInputValue(val)
    setUserEditing(true)

    const result = getParameterInputSchema(parameter).safeParse(val)
    setError(
      result.success ? null : result.error.errors[0]?.message || "Invalid",
    )
  }

  const handleSave = async (mode: "update" | "default") => {
    if (error || isReadOnly) return

    const result = getParameterInputSchema(parameter).safeParse(inputValue)
    if (!result.success) return

    if (mode === "update") {
      await updateParameter(inputValue)
    } else {
      setNodes((nodes) =>
        nodes.map((n) =>
          n.id === operatorCanonicalID
            ? {
                ...n,
                data: {
                  ...n.data,
                  parameters: n.data.parameters?.map((p) =>
                    p.name === parameter.name
                      ? { ...p, default: result.data, value: result.data }
                      : p,
                  ),
                },
              }
            : n,
        ),
      )
      if (isRuntimeMode) saveRevision(getNodes(), getEdges())
    }
    setUserEditing(false)
  }

  const parsedInput = getParameterNativeValue(parameter, inputValue)
  const hasChanged =
    !error &&
    !isReadOnly &&
    parsedInput !== undefined &&
    currentValue !== parsedInput

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="flex-start">
        <Box sx={{ flex: 1 }}>
          <NodeFieldInput
            fieldType={parameter.type as NodeFieldType}
            name={parameter.name}
            label={parameter.label}
            value={inputValue}
            options={
              parameter.type === "str-enum" ? (parameter as any).options : []
            }
            disabled={isReadOnly}
            error={error ?? null}
            onChange={handleValueChange}
          />
        </Box>
        <Box sx={{ pt: 1 }}>
          <ParameterInfoTooltip parameter={parameter} />
        </Box>
      </Stack>

      {hasChanged && (
        <Box sx={{ mt: 1, display: "flex", justifyContent: "flex-end" }}>
          <Button
            variant="contained"
            size="small"
            onClick={() => handleSave(isRuntimeMode ? "update" : "default")}
          >
            {isRuntimeMode ? "Update" : "Set Default"}
          </Button>
        </Box>
      )}
    </Box>
  )
}

export default memo(ParameterUpdater)
