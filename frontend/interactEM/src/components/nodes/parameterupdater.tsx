import {
  Box,
  Button,
  Container,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  TextField,
  Typography,
} from "@mui/material"
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
  type ParameterValue,
  getParameterSchema,
  stringifyParameterValue,
} from "../../types/params"
import ParameterInfoTooltip from "./parameterinfotooltip"

type ParameterUpdaterProps = {
  parameter: OperatorSpecParameter
  operatorCanonicalID: string
}

const ParameterUpdater: React.FC<ParameterUpdaterProps> = ({
  parameter,
  operatorCanonicalID,
}) => {
  const { viewMode } = useViewModeStore()
  const { selectedRuntimePipelineId } = usePipelineStore()
  const { isInRunningPipeline } =
    useOperatorInSelectedPipeline(operatorCanonicalID)

  const { getNode, setNodes, getEdges, getNodes } =
    useReactFlow<OperatorNodeType>()

  // Build Zod schema for this parameter
  const schema = getParameterSchema(parameter)

  const parsedDefaultValue = schema.safeParse(parameter.default)
  const defaultValue = (
    parsedDefaultValue.success ? parsedDefaultValue.data : parameter.default
  ) as ParameterValue
  const defaultString = stringifyParameterValue(defaultValue)
  const { actualValue: runtimeValue, hasReceivedMessage } = useParameterAck(
    operatorCanonicalID,
    parameter.name,
    defaultString,
  )
  const parsedRuntimeValue = schema.safeParse(runtimeValue)

  const { saveRevision } = useSavePipelineRevision()
  const { mutateAsync: updateParameter } = useParameterUpdate(
    operatorCanonicalID,
    parameter,
  )

  const node = getNode(operatorCanonicalID)
  if (!node) {
    throw new Error(`Node with id ${operatorCanonicalID} not found`)
  }

  // In Runtime mode, check if we have a selected runtime pipeline deployment AND operator is in it
  const hasRuntimePipeline = !!selectedRuntimePipelineId && isInRunningPipeline

  const comparisonTarget =
    viewMode === ViewMode.Runtime && hasRuntimePipeline
      ? hasReceivedMessage
        ? parsedRuntimeValue.success
          ? (parsedRuntimeValue.data as ParameterValue)
          : defaultValue
        : defaultValue
      : defaultValue

  const [inputValue, setInputValue] = useState<string>(
    stringifyParameterValue(comparisonTarget),
  )
  const [error, setError] = useState(false)
  const [errorMessage, setErrorMessage] = useState("")
  const [userEditing, setUserEditing] = useState(false)

  const isReadOnly = viewMode === ViewMode.Runtime ? !hasRuntimePipeline : false

  useEffect(() => {
    if (!userEditing || isReadOnly) {
      setInputValue(stringifyParameterValue(comparisonTarget))
    }
    if (isReadOnly) {
      setUserEditing(false)
    }
  }, [comparisonTarget, isReadOnly, userEditing])

  const validateInput = (value: string) => schema.safeParse(value)

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    if (isReadOnly) return
    const newValue = e.target.value
    setInputValue(newValue)
    setUserEditing(true)

    const result = validateInput(newValue)
    if (!result.success) {
      setError(true)
      setErrorMessage(result.error.errors[0]?.message || "Invalid value")
      return
    }
    setError(false)
    setErrorMessage("")
  }

  const updateNodeParameter = (updateFn: (p: any) => any) => {
    setNodes((nodes) =>
      nodes.map((n) =>
        n.id === operatorCanonicalID
          ? {
              ...n,
              data: {
                ...n.data,
                parameters: n.data.parameters?.map((p) =>
                  p.name === parameter.name ? updateFn(p) : p,
                ),
              },
            }
          : n,
      ),
    )
  }

  const compareValues = (value1: ParameterValue, value2: string): boolean => {
    const parsed1 = schema.safeParse(value1)
    const parsed2 = schema.safeParse(value2)
    if (!parsed1.success || !parsed2.success) return false
    return parsed1.data === parsed2.data
  }

  const handleUpdateClick = async () => {
    if (error || isReadOnly) return

    const result = schema.safeParse(inputValue)
    if (!result.success) {
      setError(true)
      setErrorMessage(result.error.errors[0]?.message || "Invalid value")
      return
    }

    const parsedValue = result.data
    updateNodeParameter((p) => ({ ...p, value: parsedValue }))
    await updateParameter(stringifyParameterValue(parsedValue))
    setUserEditing(false)
  }

  const handleSetDefaultClick = () => {
    if (error) return
    const result = schema.safeParse(inputValue)
    if (!result.success) return

    const parsedValue = result.data
    updateNodeParameter((p) => ({
      ...p,
      default: parsedValue,
      value: parsedValue,
    }))
    if (viewMode === ViewMode.Runtime && hasRuntimePipeline) {
      saveRevision(getNodes(), getEdges())
    }
    setUserEditing(false)
  }

  const renderInputField = () => {
    switch (parameter.type) {
      case "int":
      case "float":
      case "str":
      case "mount":
        return (
          <TextField
            value={inputValue}
            size="small"
            label="Set Point"
            variant="outlined"
            onChange={handleInputChange}
            error={error}
            helperText={error ? errorMessage : ""}
            sx={{ flexGrow: 1 }}
            disabled={isReadOnly}
          />
        )
      case "str-enum":
        return (
          <FormControl fullWidth size="small" disabled={isReadOnly}>
            <InputLabel id={`${parameter.name}-label`}>Set Point</InputLabel>
            <Select
              labelId={`${parameter.name}-label`}
              value={inputValue}
              label="Set Point"
              onChange={(e) => {
                if (isReadOnly) return
                setInputValue(e.target.value as string)
                setUserEditing(true)
                setError(false)
              }}
            >
              {parameter.options?.map((option) => (
                <MenuItem key={option} value={option}>
                  {option}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )
      case "bool":
        return (
          <FormControlLabel
            control={
              <Switch
                checked={inputValue === "true"}
                onChange={(e) => {
                  if (isReadOnly) return
                  const val = e.target.checked ? "true" : "false"
                  setInputValue(val)
                  setUserEditing(true)
                  setError(false)
                }}
                disabled={isReadOnly}
              />
            }
            label="Set Point"
          />
        )
      default:
        return null
    }
  }

  const showButtons =
    !error && !isReadOnly && !compareValues(comparisonTarget, inputValue)

  return (
    <Container>
      <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
        <Typography sx={{ fontSize: 16 }}>{parameter.label}</Typography>
        <ParameterInfoTooltip parameter={parameter} />
      </Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
        {renderInputField()}
        {showButtons &&
          (viewMode === ViewMode.Runtime && hasRuntimePipeline ? (
            // Runtime mode → only allow Update
            <Button
              variant="contained"
              color="primary"
              size="small"
              onClick={handleUpdateClick}
            >
              Update
            </Button>
          ) : (
            // Design/Edit mode → only allow Set Default
            <Button
              variant="contained"
              color="primary"
              size="small"
              onClick={handleSetDefaultClick}
            >
              Set Default
            </Button>
          ))}
      </Box>
      {error && (
        <Typography color="error">Failed to update parameter</Typography>
      )}
    </Container>
  )
}

export default memo(ParameterUpdater)
