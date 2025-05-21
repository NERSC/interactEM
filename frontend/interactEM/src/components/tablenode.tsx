import { Box, Typography } from "@mui/material"
import type { NodeProps } from "@xyflow/react"
import { useRef } from "react"
import { useTableData } from "../hooks/useTableData"
import type { TableNodeType } from "../types/nodes"
import Handles from "./handles"
import { withOperatorStatus } from "./operatorstatuscontrol"
import TableView from "./table"

interface TableNodeBaseProps extends NodeProps<TableNodeType> {
  className?: string
}

const TableNodeBase = ({ id, data, className = "" }: TableNodeBaseProps) => {
  const nodeRef = useRef<HTMLDivElement>(null)
  const tablePayload = useTableData(id)

  return (
    <Box ref={nodeRef} className={`operator ${className}`}>
      <Handles inputs={data.inputs} outputs={data.outputs} />
      <Typography variant="subtitle2">
        {tablePayload ? "" : "Waiting for table data..."}
      </Typography>
      <TableView tablePayload={tablePayload} />
    </Box>
  )
}

const TableNode = withOperatorStatus(TableNodeBase)

export default TableNode
