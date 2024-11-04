import type React from "react"

interface OperatorHeaderProps {
  label: string
}

const OperatorHeader: React.FC<OperatorHeaderProps> = ({ label }) => {
  return <div className="operator-header">{label}</div>
}

export default OperatorHeader
