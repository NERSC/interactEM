import InfoIcon from "@mui/icons-material/Info"
import { IconButton, Tooltip } from "@mui/material"
import { useNodesData } from "@xyflow/react"
import type React from "react"
import type { OperatorSpecParameter, OperatorSpecTag } from "../../client"
import type { OperatorNodeType } from "../../types/nodes"
import ParametersButton from "./parametersbutton"

interface OperatorToolbarProps {
  id: string
  image: string
  parameters?: OperatorSpecParameter[] | null
  nodeRef: React.RefObject<HTMLDivElement>
}

const OperatorToolbar: React.FC<OperatorToolbarProps> = ({
  id,
  image,
  parameters,
  nodeRef,
}) => {
  const nodeData = useNodesData<OperatorNodeType>(id)
  const nodeTags = nodeData?.data.tags || []

  return (
    <div className="operator-toolbar">
      <div className="operator-icons">
        {parameters && (
          <ParametersButton
            operatorID={id}
            parameters={parameters}
            nodeRef={nodeRef}
          />
        )}

        <Tooltip
          title={
            <div>
              <div>Image: {image}</div>
              {nodeTags.length > 0 && (
                <div>
                  Tags:
                  <ul style={{ margin: "5px 0", paddingLeft: "20px" }}>
                    {nodeTags.map((tag: OperatorSpecTag, index: number) => (
                      <li key={index}>
                        {tag.value}
                        {tag.description && (
                          <div>
                            <em>{tag.description}</em>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          }
          placement="top"
        >
          <IconButton size="small" aria-label="Info">
            <InfoIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </div>
    </div>
  )
}

export default OperatorToolbar
