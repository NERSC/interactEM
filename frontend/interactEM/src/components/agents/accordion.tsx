import ExpandMoreIcon from "@mui/icons-material/ExpandMore"
import PeopleIcon from "@mui/icons-material/People"
import { Accordion, AccordionDetails, AccordionSummary } from "@mui/material"
import { useAllAgents } from "../../hooks/nats/useAgents"
import AgentsArray from "./array"

export default function AgentsAccordion() {
  const { agents } = useAllAgents()
  return (
    <Accordion
      disableGutters
      sx={{
        background: "rgba(255, 255, 255, 0.8)",
        width: "auto",
        alignSelf: "center",
        "&.MuiPaper-root": {
          overflowX: "visible",
        },
        // Prevent box from shifting
        "&.Mui-expanded": {
          margin: 0,
        },
        // Remove any top border/line
        "&:before": {
          display: "none",
        },
      }}
    >
      <AccordionSummary
        expandIcon={<ExpandMoreIcon />}
        aria-controls="agents-panel-content"
        id="agents-panel-header"
        sx={{
          minHeight: 48,
          py: 0,
          // Prevent summary from shifting when expanded
          "&.Mui-expanded": {
            minHeight: 48,
            margin: 0,
          },
          // Prevent content from shifting
          "& .MuiAccordionSummary-content": {
            margin: "12px 0",
            "&.Mui-expanded": {
              margin: "12px 0",
            },
          },
        }}
      >
        <PeopleIcon sx={{ mr: 1 }} />
        Agents {`(${agents.length})`}
      </AccordionSummary>
      <AccordionDetails
        sx={{
          p: 0,
          width: "max-content",
          backgroundColor: "rgba(255, 255, 255, 0.9)",
        }}
      >
        <AgentsArray agents={agents} hideTitle={true} />
      </AccordionDetails>
    </Accordion>
  )
}
