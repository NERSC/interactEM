import SettingsIcon from "@mui/icons-material/Settings"
import { Typography } from "@mui/material"
import type React from "react"
import type { OperatorSpecParameter } from "../../client"
import NodeModalButton from "./nodemodalbutton"
import ParameterUpdater from "./parameterupdater"

const ParametersButton: React.FC<{
  operatorID: string
  parameters: OperatorSpecParameter[]
  nodeRef: React.RefObject<HTMLDivElement>
}> = ({ operatorID, parameters, nodeRef }) => {
  return (
    <NodeModalButton
      nodeRef={nodeRef}
      icon={<SettingsIcon fontSize="small" />}
      label="Parameters"
      title={null}
    >
      {parameters.map((param) => (
        <ParameterUpdater
          key={param.name}
          parameter={param}
          operatorCanonicalID={operatorID}
        />
      ))}
      {parameters.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No parameters available.
        </Typography>
      )}
    </NodeModalButton>
  )
}

export default ParametersButton
