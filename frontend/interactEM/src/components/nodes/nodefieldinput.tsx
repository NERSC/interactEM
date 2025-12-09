import {
  Box,
  FormControl,
  FormControlLabel,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  TextField,
  Typography,
} from "@mui/material"
import type { SxProps, Theme } from "@mui/material"
import type React from "react"
import type { OperatorSpecParameter } from "../../client"
import type { ParameterSpecType } from "../../types/gen"

export type NodeFieldType = ParameterSpecType | OperatorSpecParameter["type"]

type NodeFieldInputProps = {
  name: string
  fieldType: NodeFieldType
  label: string
  value: string
  onChange: (value: string) => void
  description?: string | null
  options?: string[]
  required?: boolean
  disabled?: boolean
  error?: string | boolean | null // Pass error message string here directly if possible
  helperText?: string
  sx?: SxProps<Theme> // Only for the outer container
}

const NO_SPINNERS: SxProps<Theme> = {
  "& input[type=number]": {
    "&::-webkit-outer-spin-button, &::-webkit-inner-spin-button": {
      display: "none",
    },
    MozAppearance: "textfield",
  },
}

// decide what text to show below the input
const getHelperText = (
  error: string | boolean | null | undefined,
  helperText: string | undefined,
  description: string | null | undefined,
  required: boolean,
) => {
  if (typeof error === "string" && error.length > 0) return error
  if (helperText) return helperText
  if (description) return description
  return !required ? "Optional" : undefined
}

const NodeFieldInput: React.FC<NodeFieldInputProps> = ({
  name,
  fieldType,
  label,
  value,
  onChange,
  options = [],
  description,
  required = true,
  disabled,
  error,
  helperText,
  sx,
}) => {
  const displayHelperText = getHelperText(
    error,
    helperText,
    description,
    required,
  )
  const hasError = !!error
  const labelId = `${name}-label`

  // 1. NUMBER / STRING INPUTS
  if (["int", "float", "str", "mount"].includes(fieldType)) {
    const isNumber = fieldType === "int" || fieldType === "float"
    return (
      <Box sx={sx}>
        <TextField
          label={label}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          type={isNumber ? "number" : "text"}
          fullWidth
          size="small"
          disabled={disabled}
          error={hasError}
          helperText={displayHelperText}
          sx={isNumber ? NO_SPINNERS : undefined}
        />
      </Box>
    )
  }

  // 2. SELECT INPUT (ENUM)
  if (fieldType === "str-enum") {
    return (
      <Box sx={sx}>
        <FormControl
          fullWidth
          size="small"
          error={hasError}
          disabled={disabled}
        >
          <InputLabel id={labelId}>{label}</InputLabel>
          <Select
            labelId={labelId}
            value={value}
            label={label}
            onChange={(e) => onChange(e.target.value)}
          >
            {options.map((opt) => (
              <MenuItem key={opt} value={opt}>
                {opt}
              </MenuItem>
            ))}
          </Select>
          {displayHelperText && (
            <FormHelperText>{displayHelperText}</FormHelperText>
          )}
        </FormControl>
      </Box>
    )
  }

  // 3. BOOLEAN SWITCH
  if (fieldType === "bool") {
    return (
      <Box sx={sx}>
        <FormControl
          component="fieldset"
          variant="standard"
          error={hasError}
          disabled={disabled}
        >
          <FormControlLabel
            control={
              <Switch
                checked={value === "true"}
                onChange={(e) => onChange(e.target.checked ? "true" : "false")}
              />
            }
            label={
              <Box>
                <Typography variant="body2">{label}</Typography>
                {description && (
                  <Typography variant="caption" color="text.secondary">
                    {description}
                  </Typography>
                )}
              </Box>
            }
            labelPlacement="start"
          />
          {/* only show if there is an actual error */}
          {(hasError || helperText) && (
            <FormHelperText>{displayHelperText}</FormHelperText>
          )}
        </FormControl>
      </Box>
    )
  }

  console.warn(`Unsupported fieldType: ${fieldType}`)
  return null
}

export default NodeFieldInput
