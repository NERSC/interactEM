import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material"
import type React from "react"
import type {
  TablePayload,
  TableRow as TableRowData,
} from "../hooks/useTableData"

interface TableViewProps {
  tablePayload: TablePayload | null
}

// Put styles here to prevent re-renders caused by sx prop
const italicStyle = { fontStyle: "italic" }
const mediumWeightStyle = { fontWeight: "medium" }
const tableHeadStyle = { backgroundColor: "grey.100" }
const tableHeadCellStyle = { fontWeight: "bold", py: 0.5 }
const tableRowStyle = {
  "&:last-child td, &:last-child th": { border: 0 },
  "&:nth-of-type(odd)": { backgroundColor: "action.hover" },
}
const tableCellStyle = { py: 0.5 }
const waitingTextStyle = { p: 1, fontStyle: "italic" }
const containerBoxStyle = { padding: 1, maxHeight: 450, overflowY: "auto" }

const renderTable = (tableName: string, data: TableRowData[]) => {
  if (!data || data.length === 0) {
    return (
      <Typography
        key={tableName}
        variant="subtitle2"
        gutterBottom
        sx={italicStyle}
      >
        Table '{tableName}': No data.
      </Typography>
    )
  }

  const firstRow = data[0]
  if (!firstRow) {
    return (
      <Typography
        key={tableName}
        variant="subtitle2"
        gutterBottom
        sx={italicStyle}
      >
        Table '{tableName}': Contains an empty first row.
      </Typography>
    )
  }
  const headers = Object.keys(firstRow)

  return (
    <Box key={tableName} mb={2}>
      <Typography variant="subtitle1" gutterBottom sx={mediumWeightStyle}>
        {tableName}
      </Typography>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" aria-label={`${tableName} table`}>
          <TableHead sx={tableHeadStyle}>
            <TableRow>
              {headers.map((header) => (
                <TableCell key={header} sx={tableHeadCellStyle}>
                  {header}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {data.map((row, index) => (
              <TableRow key={index} sx={tableRowStyle}>
                {headers.map((header) => (
                  <TableCell
                    key={`${index}-${header}`}
                    component="th"
                    scope="row"
                    sx={tableCellStyle}
                  >
                    {row && typeof row === "object" && header in row
                      ? typeof row[header] === "boolean"
                        ? row[header]
                          ? "true"
                          : "false"
                        : String(row[header] ?? "")
                      : ""}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  )
}

const TableView: React.FC<TableViewProps> = ({ tablePayload }) => {
  if (!tablePayload || !tablePayload.tables) {
    return (
      <Typography sx={waitingTextStyle}>Waiting for table data...</Typography>
    )
  }

  const tablesDict = tablePayload.tables
  const tableNames = Object.keys(tablesDict)

  return (
    <Box className="no-wheel" sx={containerBoxStyle}>
      {tableNames.length > 0 ? (
        tableNames.map((tableName) => {
          const tableData = tablesDict[tableName]
          return Array.isArray(tableData)
            ? renderTable(tableName, tableData)
            : null
        })
      ) : (
        <Typography sx={waitingTextStyle}>
          No tables found in the data.
        </Typography>
      )}
    </Box>
  )
}

export default TableView
