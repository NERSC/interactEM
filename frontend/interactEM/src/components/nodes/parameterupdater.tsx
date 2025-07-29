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
import type React from "react"
import { memo, useEffect, useState } from "react"
import type { OperatorSpecParameter } from "../../client"
import { usePipelineContext } from "../../contexts/pipeline"
import { useParameterUpdate } from "../../hooks/nats/useParameterUpdate"
import { useParameterAck } from "../../hooks/nats/useParameterValue"
import { useEditModeState } from "../../stores/edit"
import type { OperatorNodeType } from "../../types/nodes"
import ParameterInfoTooltip from "./parameterinfotooltip"

const compareValues = (
  parameter: OperatorSpecParameter,
  value1: string,
  value2: string,
): boolean => {
  switch (parameter.type) {
    case "int":
      return Number.parseInt(value1, 10) === Number.parseInt(value2, 10)
    case "float":
      return Number.parseFloat(value1) === Number.parseFloat(value2)
    case "bool":
      return value1 === value2
    case "str":
    case "str-enum":
    case "mount":
      return value1 === value2
    default:
      return false
  }
}

type ParameterUpdaterProps = {
  parameter: OperatorSpecParameter
  operatorID: string
}

const ParameterUpdater: React.FC<ParameterUpdaterProps> = ({
  parameter,
  operatorID,
}) => {
  const { isCurrentPipelineRunning } = usePipelineContext()
  const { isEditMode } = useEditModeState()
  const { getNode, setNodes } = useReactFlow<OperatorNodeType>()
  const { actualValue: runtimeValue, hasReceivedMessage } = useParameterAck(
    operatorID,
    parameter.name,
    parameter.default,
  )

  const node = getNode(operatorID)
  if (!node) {
    throw new Error(`Node with id ${operatorID} not found`)
  }

  // Get the correct value depending on our mode
  const comparisonTarget = isCurrentPipelineRunning
    ? // If we haven't received a message use the parameter default.
      hasReceivedMessage
      ? runtimeValue
      : parameter.default
    : parameter.default

  const [inputValue, setInputValue] = useState<string>(comparisonTarget)
  const [error, setError] = useState(false)
  const [errorMessage, setErrorMessage] = useState("")
  const [userEditing, setUserEditing] = useState(false)

  const isReadOnly = !isCurrentPipelineRunning && !isEditMode

  // Update the input value when critical parameters or mode change
  useEffect(() => {
    // Only update if we haven't received user edits or we're in read-only mode
    if (!userEditing || isReadOnly) {
      setInputValue(comparisonTarget)
    }

    // Reset userEditing state when switching modes
    if (isReadOnly) {
      setUserEditing(false)
    }
  }, [comparisonTarget, isReadOnly, userEditing])

  const validateInput = (value: string) => {
    switch (parameter.type) {
      case "int":
        return /^-?\d+$/.test(value)
      case "float":
        return /^-?\d+(\.\d+)?$/.test(value)
      case "str":
      case "str-enum":
        return true
      case "bool":
        return value === "true" || value === "false"
      case "mount":
        return /^(\/|~\/)(?!.*(?:^|\/)\.\.(?:\/|$)).*$/.test(value)
      default:
        return false
    }
  }

  const {
    mutate: updateParameter,
    isPending,
    isError,
  } = useParameterUpdate(operatorID, parameter)

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    if (isReadOnly) return

    e.preventDefault()
    const newValue = e.target.value
    setInputValue(newValue)
    setUserEditing(true)

    if (!validateInput(newValue)) {
      setError(true)
      setErrorMessage("Invalid value (type mismatch)")
      return
    }
    setError(false)
  }

  const handleUpdateClick = async () => {
    if (error || isReadOnly) {
      return
    }

    setNodes((nodes) =>
      nodes.map((n) => {
        if (n.id === operatorID) {
          const updatedParameters = n.data.parameters?.map((p) => {
            if (p.name === parameter.name) {
              if (isCurrentPipelineRunning) {
                // Update value only when running
                return { ...p, value: inputValue }
              }
              // Set both default and value when not running
              return { ...p, default: inputValue, value: inputValue }
            }
            return p
          })
          return {
            ...n,
            data: {
              ...n.data,
              parameters: updatedParameters,
            },
          }
        }
        return n
      }),
    )

    updateParameter(inputValue)
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
            sx={{
              flexGrow: 1,
              "& .MuiInputBase-input.Mui-disabled": {
                WebkitTextFillColor: "rgba(0, 0, 0, 0.7)",
              },
            }}
            disabled={isReadOnly}
          />
        )
      case "str-enum":
        return (
          <FormControl
            fullWidth
            size="small"
            sx={{ flexGrow: 1 }}
            disabled={isReadOnly}
          >
            <InputLabel id={`${parameter.name}-label`}>Set Point</InputLabel>
            <Select
              labelId={`${parameter.name}-label`}
              value={inputValue}
              label="Set Point"
              onChange={(e) => {
                if (isReadOnly) return
                const newValue = e.target.value as string
                setInputValue(newValue)
                setUserEditing(true)
              }}
              inputProps={{ readOnly: isReadOnly }}
              sx={{ opacity: isReadOnly ? 0.7 : 1 }}
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
                  const newValue = e.target.checked ? "true" : "false"
                  setInputValue(newValue)
                  setUserEditing(true)
                }}
                disabled={isReadOnly}
              />
            }
            label="Set Point"
            sx={{ opacity: isReadOnly ? 0.7 : 1 }}
          />
        )
      default:
        return null
    }
  }

  useEffect(() => {
    // TODO: we should make a ParameterErrorEvent type
    if (isError || compareValues(parameter, runtimeValue, "ERROR")) {
      if (parameter.type === "mount") {
        setErrorMessage("Invalid mount. File/dir doesn't exist.")
      }
    }
  }, [parameter, isError, runtimeValue])

  const buttonVisible =
    !error &&
    !isReadOnly &&
    !compareValues(parameter, comparisonTarget, inputValue) &&
    !isPending

  return (
    <Container>
      <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
        <Typography sx={{ fontSize: 16 }}>{parameter.label}</Typography>
        <ParameterInfoTooltip parameter={parameter} />
      </Box>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          flexGrow: 1,
        }}
      >
        {renderInputField()}
        {buttonVisible && (
          <Button
            type="submit"
            variant="contained"
            color="primary"
            size="small"
            onClick={handleUpdateClick}
          >
            {isCurrentPipelineRunning ? "Update" : "Set Default"}
          </Button>
        )}
      </Box>
      {isError && (
        <Typography color="error">Failed to update parameter</Typography>
      )}
    </Container>
  )
}

export default memo(ParameterUpdater)
