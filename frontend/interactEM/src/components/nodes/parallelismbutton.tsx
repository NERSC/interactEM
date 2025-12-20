import LanIcon from "@mui/icons-material/Lan"
import { Box, Button, Stack, TextField, Typography } from "@mui/material"
import { useNodesData, useReactFlow } from "@xyflow/react"
import { type RefObject, useEffect, useMemo, useState } from "react"
import { zCanonicalOperator } from "../../client/generated/zod.gen"
import { useSavePipelineRevision } from "../../hooks/api/useSavePipelineRevision"
import { ViewMode, useViewModeStore } from "../../stores"
import { ParallelType } from "../../types/gen"
import type { OperatorNodeType } from "../../types/nodes"
import NodeModalButton from "./nodemodalbutton"

interface ParallelismButtonProps {
  operatorID: string
  nodeRef: RefObject<HTMLDivElement>
}

const ParallelismButton: React.FC<ParallelismButtonProps> = ({
  operatorID,
  nodeRef,
}) => {
  const nodeData = useNodesData<OperatorNodeType>(operatorID)
  const { viewMode } = useViewModeStore()
  const { setNodes, getEdges } = useReactFlow<OperatorNodeType>()
  const { saveRevision } = useSavePipelineRevision()
  const [inputValue, setInputValue] = useState<string>("")
  const [error, setError] = useState<string | null>(null)

  const supportsParallelism = useMemo(() => {
    return (
      nodeData?.data.parallel_config?.type === ParallelType.embarrassing &&
      viewMode === ViewMode.Composer
    )
  }, [nodeData?.data.parallel_config?.type, viewMode])

  useEffect(() => {
    setInputValue(nodeData?.data.parallelism?.toString() ?? "")
    setError(null)
  }, [nodeData?.data.parallelism])

  if (!nodeData || !supportsParallelism) return null

  const currentParallelism =
    nodeData.data.parallelism === undefined ? null : nodeData.data.parallelism

  const validateValue = (
    value: string,
  ): { parsed: number | null; error: string | null } => {
    const trimmed = value.trim()
    if (!trimmed) return { parsed: null, error: null }

    const parsed = Number(trimmed)
    const validation = zCanonicalOperator.shape.parallelism.safeParse(parsed)
    if (!validation.success) {
      return {
        parsed: null,
        error: validation.error.issues[0]?.message ?? "Invalid parallelism",
      }
    }

    return { parsed, error: null }
  }

  const handleChange = (value: string) => {
    setInputValue(value)
    const { error: validationError } = validateValue(value)
    setError(validationError)
  }

  const handleSave = () => {
    const { parsed, error: validationError } = validateValue(inputValue)
    if (validationError) {
      setError(validationError)
      return
    }

    setNodes((nodes) => {
      const updatedNodes = nodes.map((node) =>
        node.id === operatorID
          ? { ...node, data: { ...node.data, parallelism: parsed } }
          : node,
      )

      saveRevision(updatedNodes, getEdges())
      return updatedNodes
    })
  }

  const handleReset = () => {
    setInputValue("")
    setError(null)

    if (currentParallelism === null) {
      return
    }

    setNodes((nodes) => {
      const updatedNodes = nodes.map((node) =>
        node.id === operatorID
          ? { ...node, data: { ...node.data, parallelism: null } }
          : node,
      )

      saveRevision(updatedNodes, getEdges())
      return updatedNodes
    })
  }

  const helperText =
    error ??
    (currentParallelism === null
      ? "Using the system default; enter a value to override it"
      : "Leave blank or reset to use the system default parallelism")
  const resetDisabled =
    currentParallelism === null && inputValue.trim().length === 0

  return (
    <NodeModalButton
      nodeRef={nodeRef}
      icon={<LanIcon fontSize="small" />}
      label="Parallelism"
      title="Parallelism"
    >
      <Stack spacing={1.5}>
        <Typography variant="body2" color="text.secondary">
          Control how many parallel copies of this operator will be launched
          when the pipeline is deployed. 
        </Typography>

        <Typography variant="body2" color="text.secondary">
          Current setting:{" "}
          {currentParallelism === null
            ? "Using system default parallelism"
            : `${currentParallelism} parallel ${
                currentParallelism === 1 ? "copy" : "copies"
              }`}
        </Typography>

        <TextField
          label="Parallel copies"
          value={inputValue}
          onChange={(event) => handleChange(event.target.value)}
          type="number"
          fullWidth
          size="small"
          error={!!error}
          helperText={helperText}
        />

        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 1,
          }}
        >
          <Button
            variant="outlined"
            size="small"
            onClick={handleReset}
            disabled={resetDisabled}
          >
            Reset to default
          </Button>

          <Button
            variant="contained"
            size="small"
            onClick={handleSave}
            disabled={!!error}
          >
            Save
          </Button>
        </Box>
      </Stack>
    </NodeModalButton>
  )
}

export default ParallelismButton
