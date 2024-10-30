import type React from "react"
import { memo, useEffect, useState } from "react"
import TextField from "@mui/material/TextField"
import Button from "@mui/material/Button"
import Typography from "@mui/material/Typography"
import Box from "@mui/material/Box"
import { Container, Switch, FormControlLabel } from "@mui/material"
import type { OperatorParameter } from "../operators"
import { useParameterValue } from "../hooks/useParameterValue"
import { useParameterUpdate } from "../hooks/useParameterUpdate"

type ParameterUpdaterProps = {
  parameter: OperatorParameter
  operatorID: string
}

const ParameterUpdater: React.FC<ParameterUpdaterProps> = ({
  parameter,
  operatorID,
}) => {
  const actualValue = useParameterValue(operatorID, parameter)
  const [inputValue, setInputValue] = useState(actualValue)
  const [error, setError] = useState(false)

  const {
    mutate: updateParameter,
    isPending,
    isError,
  } = useParameterUpdate(operatorID, parameter)

  useEffect(() => {
    if (actualValue !== parameter.default) {
      setInputValue(actualValue)
    }
  }, [actualValue, parameter.default])

  const validateInput = (value: string) => {
    switch (parameter.type) {
      case "int":
        return /^-?\d+$/.test(value)
      case "float":
        return /^-?\d+(\.\d+)?$/.test(value)
      case "string":
        return true
      case "bool":
        return value === "true" || value === "false"
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
    const isValid = validateInput(newValue)
    setError(!isValid)
  }

  const handleUpdateClick = async () => {
    if (error) {
      return
    }
    updateParameter(inputValue)
  }

  const renderInputField = () => {
    switch (parameter.type) {
      case "int":
      case "float":
      case "string":
        return (
          <TextField
            value={inputValue}
            size="small"
            label="Set Point"
            variant="outlined"
            onChange={handleInputChange}
            error={error}
            helperText={error ? `Invalid ${parameter.type} value` : ""}
            sx={{ width: "100px", flexGrow: 1 }}
          />
        )
      case "bool":
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
        <TextField
          type="text"
          disabled
          size="small"
          label="Actual Value"
          variant="outlined"
          value={actualValue}
          sx={{ width: "auto", flexGrow: 1 }}
        />
        <Button
          type="submit"
          variant="contained"
          color="primary"
          size="small"
          onClick={handleUpdateClick}
          disabled={isPending || error}
        >
          Update
        </Button>
      </Box>
      {isError && (
        <Typography color="error">Failed to update parameter</Typography>
      )}
    </Container>
  )
}

export default memo(ParameterUpdater)
