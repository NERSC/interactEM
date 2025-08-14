import { Box, Typography } from "@mui/material"
import type { NodeProps } from "@xyflow/react"
import { useRef } from "react"
import { useRuntimeOperatorStatusStyles } from "../../hooks/nats/useOperatorStatus"
import { useTableData } from "../../hooks/nats/useTableData"
import type { TableNodeType } from "../../types/nodes"
import TableView from "../table"
import Handles from "./handles"

interface TableNodeBaseProps extends NodeProps<TableNodeType> {
  className?: string
}

const TableNodeBase = ({ id, data, className = "" }: TableNodeBaseProps) => {
  const nodeRef = useRef<HTMLDivElement>(null)
  const tablePayload = useTableData(id)
  const { statusClass } = useRuntimeOperatorStatusStyles(id)

  return (
    <Box ref={nodeRef} className={`operator ${className} ${statusClass}`}>
      <Handles inputs={data.inputs} outputs={data.outputs} />
      <Typography variant="subtitle2">
        {tablePayload ? "" : "Waiting for table data..."}
      </Typography>
      <TableView tablePayload={tablePayload} />
    </Box>
  )
}

const TableNode = TableNodeBase

export default TableNode
