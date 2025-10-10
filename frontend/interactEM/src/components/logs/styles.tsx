import { Box, IconButton, Paper, Typography } from "@mui/material"
import { styled } from "@mui/material/styles"
import type React from "react"

export const LogsPanel = styled(Paper)(({ theme }) => ({
  backgroundColor:
    theme.palette.mode === "dark" ? theme.palette.background.paper : "#1e1e1e",
  padding: theme.spacing(2),
  height: "60vh",
  fontFamily: "monospace",
  fontSize: "0.85rem",
}))

export const CloseDialogButton = styled(IconButton)(({ theme }) => ({
  position: "absolute",
  right: theme.spacing(1),
  top: theme.spacing(1),
  color: theme.palette.grey[500],
}))

export const LogRow = styled(Box)({
  marginBottom: 4,
  display: "flex",
  gap: 8,
})

export const LogTimestamp = styled("span")(({ theme }) => ({
  color:
    theme.palette.mode === "dark"
      ? theme.palette.text.primary
      : theme.palette.grey[300],
  minWidth: "90px",
}))

const LogLevelSpan = styled("span")<{ level?: string }>(({ theme, level }) => {
  const colorMap: Record<string, string> = {
    error: theme.palette.error.main,
    warning: theme.palette.warning.main,
    warn: theme.palette.warning.main,
    info: theme.palette.info.main,
    debug: theme.palette.grey[500],
  }

  const color = level
    ? colorMap[level.toLowerCase()] || theme.palette.grey[500]
    : theme.palette.grey[500]

  return {
    color,
    minWidth: "60px",
    fontWeight: "bold",
  }
})

interface LogLevelProps {
  level?: string
}

export const LogLevel: React.FC<LogLevelProps> = ({ level }) => {
  return (
    <LogLevelSpan level={level}>
      {level?.toUpperCase() ?? "UNKNOWN"}
    </LogLevelSpan>
  )
}

export const LogModule = styled("span")(({ theme }) => ({
  color: theme.palette.primary.light,
  minWidth: "150px",
}))

export const LogInstance = styled("span")(({ theme }) => ({
  color: theme.palette.primary.light,
  minWidth: "40px",
}))

export const LogMessage = styled("span")(({ theme }) => ({
  color:
    theme.palette.mode === "dark"
      ? theme.palette.text.primary
      : theme.palette.grey[300],
  flex: 1,
  wordBreak: "break-word",
}))

export const EmptyLogsMessage = styled(Typography)(({ theme }) => ({
  color:
    theme.palette.mode === "dark"
      ? theme.palette.text.primary
      : theme.palette.grey[300],
}))
