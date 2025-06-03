import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined"
import { Box, IconButton, Paper, Tooltip, Typography } from "@mui/material"
import type React from "react"
import type { OperatorParameter } from "../../client/generated/types.gen"

interface ParameterInfoTooltipProps {
  parameter: OperatorParameter
}

const ParameterInfoTooltip: React.FC<ParameterInfoTooltipProps> = ({
  parameter,
}) => {
  const content = (
    <Paper sx={{ p: 1.5, maxWidth: 280 }}>
      <Typography variant="subtitle2" fontWeight="bold">
        {parameter.label}
      </Typography>
      <Typography variant="body2" sx={{ mt: 0.5 }}>
        {parameter.description}
      </Typography>
      <Box sx={{ mt: 1 }}>
        <Typography variant="caption" component="div">
          <strong>Type:</strong> {parameter.type}
        </Typography>
        <Typography variant="caption" component="div">
          <strong>Default:</strong> {parameter.default}
        </Typography>
        <Typography variant="caption" component="div">
          <strong>Required:</strong> {parameter.required ? "Yes" : "No"}
        </Typography>
        {parameter.options && parameter.options.length > 0 && (
          <Typography variant="caption" component="div">
            <strong>Options:</strong> {parameter.options.join(", ")}
          </Typography>
        )}
      </Box>
    </Paper>
  )

  return (
    <Tooltip
      title={content}
      placement="top"
      arrow
      componentsProps={{
        tooltip: { sx: { backgroundColor: "transparent", p: 0 } },
      }}
    >
      <IconButton
        size="small"
        color="inherit"
        sx={{
          ml: 0.5,
          p: 0,
          opacity: 0.7,
          "&:hover": {
            opacity: 1,
            backgroundColor: "transparent",
          },
        }}
      >
        <InfoOutlinedIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  )
}

export default ParameterInfoTooltip
