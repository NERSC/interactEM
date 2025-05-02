import { Box, Typography } from "@mui/material"
import type { NodeProps } from "@xyflow/react"
import { useRef } from "react"
import { useTableData } from "../hooks/useTableData"
import type { TableNodeType } from "../types/nodes"
import Handles from "./handles"
import TableView from "./table"

const TableNode = ({ id, data }: NodeProps<TableNodeType>) => {
  const nodeRef = useRef<HTMLDivElement>(null)
  const tablePayload = useTableData(id)

  return (
    <Box ref={nodeRef} className="operator">
      <Handles inputs={data.inputs} outputs={data.outputs} />
      <Typography variant="subtitle2">
        {tablePayload ? "" : "Waiting for table data..."}
      </Typography>
      <TableView tablePayload={tablePayload} />
    </Box>
  )
}

export default TableNode
