import Paper from "@mui/material/Paper"
import Typography from "@mui/material/Typography"
import { styled } from "@mui/material/styles"
import type { Agent } from "../../types/agent"
import AgentChip from "./chip"
import { LaunchAgentButton } from "./launchbutton"

const ListItem = styled("li")(({ theme }) => ({
  margin: theme.spacing(0.5),
}))

interface AgentsArrayProps {
  agents: Agent[]
  direction?: "horizontal" | "vertical"
  hideTitle?: boolean
}

export default function AgentsArray({
  agents,
  direction = "vertical",
  hideTitle = false,
}: AgentsArrayProps) {
  return (
    <Paper
      sx={{
        p: 1,
        background: "transparent",
      }}
      elevation={0}
    >
      {!hideTitle && (
        <Typography
          variant="subtitle1"
          sx={{
            mb: 1,
            fontWeight: 600,
            textAlign: "center",
            width: "100%",
          }}
        >
          Agents
        </Typography>
      )}
      <ul
        style={{
          display: "flex",
          flexDirection: direction === "vertical" ? "column" : "row",
          justifyContent: "flex-start",
          flexWrap: direction === "horizontal" ? "wrap" : "nowrap",
          listStyle: "none",
          padding: 0,
          margin: 0,
        }}
      >
        {agents.map((agent) => (
          <ListItem key={agent.uri.id}>
            <AgentChip agent={agent} />
          </ListItem>
        ))}
        <ListItem key="launch-agent">
          <LaunchAgentButton />
        </ListItem>
      </ul>
    </Paper>
  )
}
