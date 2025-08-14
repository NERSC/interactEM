import { Box, Divider, List, ListItem, Typography } from "@mui/material"
import { AgentValSchema } from "../../types/agent"
import type { AgentVal } from "../../types/gen"

interface AgentTooltipProps {
  data: AgentVal
}

// Reusable component for label-value pairs
const InfoItem = ({
  label,
  value,
}: { label: string; value: React.ReactNode }) => (
  <Typography variant="body2" fontWeight="medium">
    {label}:{" "}
    <Typography component="span" variant="body2">
      {value}
    </Typography>
  </Typography>
)

const formatTimestamp = (timestamp: number): string => {
  const date = new Date(timestamp * 1000)
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })
}

const AgentTooltip = ({ data: unvalidated }: AgentTooltipProps) => {
  // Format uptime to hours and minutes
  const parsed = AgentValSchema.safeParse(unvalidated)
  if (!parsed.success) {
    return <Typography color="error">Invalid agent data</Typography>
  }
  const data = parsed.data
  const formattedUptime = `${Math.floor(data.uptime / 3600)}h ${Math.floor((data.uptime % 3600) / 60)}m`

  return (
    <Box sx={{ p: 1, maxWidth: 300 }}>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
        <InfoItem label="ID" value={data.uri.id} />
        <InfoItem label="Status" value={data.status} />
        {data.tags && data.tags.length > 0 && (
          <InfoItem label="Tags" value={data.tags} />
        )}
        {data.networks && data.networks.length > 0 && (
          <InfoItem label="Networks" value={data.networks} />
        )}
        <InfoItem label="Uptime" value={formattedUptime} />
      </Box>

      {data.error_messages && data.error_messages.length > 0 && (
        <>
          <Divider sx={{ my: 1, bgcolor: "white" }} />
          <Typography variant="body2" fontWeight="medium" sx={{ mb: 0.5 }}>
            Recent Errors:
          </Typography>
          <List dense disablePadding sx={{ mt: 0.5 }}>
            {data.error_messages.map((error, index) => (
              <ListItem
                key={index}
                sx={{
                  py: 0.25,
                  flexDirection: "column",
                  alignItems: "flex-start",
                }}
              >
                <Typography variant="body2" sx={{ fontSize: "0.85rem" }}>
                  {formatTimestamp(error.timestamp)} {error.message}
                </Typography>
              </ListItem>
            ))}
          </List>
        </>
      )}
    </Box>
  )
}

export default AgentTooltip
