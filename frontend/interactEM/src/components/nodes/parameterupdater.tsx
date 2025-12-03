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
  getParameterInputSchema,
  getParameterNativeValue,
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

  const param_default = parameter.default.toString()
  const { actualValue: runtimeValue, hasReceivedMessage } = useParameterAck(
    operatorCanonicalID,
    parameter.name,
    param_default,
  )

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

  const currentValue =
    viewMode === ViewMode.Runtime && hasRuntimePipeline
      ? hasReceivedMessage
        ? runtimeValue
        : parameter.default
      : parameter.default

  // Convert to string for form display
  const displayValue = String(currentValue)

  const [inputValue, setInputValue] = useState<string>(displayValue)
  const [error, setError] = useState(false)
  const [errorMessage, setErrorMessage] = useState("")
  const [userEditing, setUserEditing] = useState(false)

  const isReadOnly = viewMode === ViewMode.Runtime ? !hasRuntimePipeline : false

  useEffect(() => {
    if (!userEditing || isReadOnly) {
      setInputValue(displayValue)
    }
    if (isReadOnly) {
      setUserEditing(false)
    }
  }, [displayValue, isReadOnly, userEditing])

  const validateInput = (value: string) => {
    const schema = getParameterInputSchema(parameter)
    return schema.safeParse(value)
  }

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

  const handleUpdateClick = async () => {
    if (error || isReadOnly) return
    updateNodeParameter((p) => ({ ...p, value: inputValue }))
    await updateParameter(inputValue)
    setUserEditing(false)
  }

  const handleSetDefaultClick = () => {
    if (error) return
    const result = validateInput(inputValue)
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
        return (
          <TextField
            type="number"
            value={inputValue}
            size="small"
            label="Set Point"
            variant="outlined"
            onChange={handleInputChange}
            error={error}
            helperText={error ? errorMessage : ""}
            sx={{
              flexGrow: 1,
              // remove arrows from number input
              "& input[type=number]": {
                "&::-webkit-outer-spin-button, &::-webkit-inner-spin-button": {
                  display: "none",
                },
                MozAppearance: "textfield",
              },
            }}
            disabled={isReadOnly}
          />
        )
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

  const parsedInputValue = getParameterNativeValue(parameter, inputValue)
  const showButtons =
    !error &&
    !isReadOnly &&
    parsedInputValue !== undefined &&
    currentValue !== parsedInputValue

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
