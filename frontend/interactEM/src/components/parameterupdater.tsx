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
import { useParameterUpdate } from "../hooks/useParameterUpdate"
import { useParameterValue } from "../hooks/useParameterValue"
import { type OperatorParameter, ParameterType } from "../operators"
import type { OperatorNode as OperatorNodeType } from "./operatornode"

const compareValues = (
  parameter: OperatorParameter,
  value1: string,
  value2: string,
): boolean => {
  switch (parameter.type) {
    case ParameterType.INTEGER:
      return Number.parseInt(value1, 10) === Number.parseInt(value2, 10)
    case ParameterType.FLOAT:
      return Number.parseFloat(value1) === Number.parseFloat(value2)
    case ParameterType.BOOLEAN:
      return value1 === value2
    case ParameterType.STRING:
    case ParameterType.STR_ENUM:
    case ParameterType.MOUNT:
      return value1 === value2
    default:
      return false
  }
}

type ParameterUpdaterProps = {
  parameter: OperatorParameter
  operatorID: string
}

const ParameterUpdater: React.FC<ParameterUpdaterProps> = ({
  parameter,
  operatorID,
}) => {
  const { getNode, setNodes } = useReactFlow<OperatorNodeType>()
  const { actualValue, hasReceivedMessage } = useParameterValue(
    operatorID,
    parameter.name,
    parameter.default,
  )
  const [inputValue, setInputValue] = useState<string>(
    parameter.value || parameter.default || "",
  )
  const [error, setError] = useState(false)
  const [errorMessage, setErrorMessage] = useState("")

  const node = getNode(operatorID)
  if (!node) {
    throw new Error(`Node with id ${operatorID} not found`)
  }

  const {
    mutate: updateParameter,
    isPending,
    isSuccess,
    isError,
  } = useParameterUpdate(operatorID, parameter)

  useEffect(() => {
    setInputValue(parameter.value || parameter.default || "")
  }, [parameter.value, parameter.default])

  const validateInput = (value: string) => {
    switch (parameter.type) {
      case ParameterType.INTEGER:
        return /^-?\d+$/.test(value)
      case ParameterType.FLOAT:
        return /^-?\d+(\.\d+)?$/.test(value)
      case ParameterType.STRING:
      case ParameterType.STR_ENUM:
        return true
      case ParameterType.BOOLEAN:
        return value === "true" || value === "false"
      case ParameterType.MOUNT:
        return /^(\/|~\/)(?!.*(?:^|\/)\.\.(?:\/|$)).*$/.test(value)
      default:
        return false
    }
  }

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    e.preventDefault()
    const newValue = e.target.value
    setInputValue(newValue)
    if (!validateInput(newValue)) {
      setError(true)
      setErrorMessage("Invalid value (type mismatch)")
      return
    }
    setError(false)
  }

  const handleUpdateClick = async () => {
    if (error) {
      return
    }

    setNodes((nodes) =>
      nodes.map((node) => {
        if (node.id === operatorID) {
          const updatedParameters = node.data.parameters?.map((p) => {
            if (p.name === parameter.name) {
              return { ...p, value: inputValue }
            }
            return p
          })
          return {
            ...node,
            data: {
              ...node.data,
              parameters: updatedParameters,
            },
          }
        }
        return node
      }),
    )

    updateParameter(inputValue)
  }

  const renderInputField = () => {
    switch (parameter.type) {
      case ParameterType.INTEGER:
      case ParameterType.FLOAT:
      case ParameterType.STRING:
      case ParameterType.MOUNT:
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
          />
        )
      case ParameterType.STR_ENUM:
        return (
          <FormControl fullWidth size="small" sx={{ flexGrow: 1 }}>
            <InputLabel id={`${parameter.name}-label`}>Set Point</InputLabel>
            <Select
              labelId={`${parameter.name}-label`}
              value={inputValue}
              label="Set Point"
              onChange={(e) => {
                const newValue = e.target.value as string
                setInputValue(newValue)
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
      case ParameterType.BOOLEAN:
        return (
          <FormControlLabel
            control={
              <Switch
                checked={inputValue === "true"}
                onChange={(e) => {
                  const newValue = e.target.checked ? "true" : "false"
                  setInputValue(newValue)
                }}
              />
            }
            label="Set Point"
          />
        )
      default:
        return null
    }
  }

  useEffect(() => {
    // TODO: we should make a ParameterErrorEvent type
    if (isError || compareValues(parameter, actualValue, "ERROR")) {
      if (parameter.type === ParameterType.MOUNT) {
        setErrorMessage("Invalid mount. File/dir doesn't exist.")
      }
    }
  }, [parameter, isError, actualValue])

  const buttonVisible =
    !error && !compareValues(parameter, actualValue, inputValue)
  const buttonDisabled = isPending

  return (
    <Container>
      <Typography sx={{ fontSize: 16, mb: 1 }}>{parameter.name}</Typography>
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
            disabled={buttonDisabled}
          >
            {hasReceivedMessage ? "Update" : "Set"}
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
