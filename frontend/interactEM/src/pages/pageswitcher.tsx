import BuildIcon from "@mui/icons-material/Build"
import VisibilityIcon from "@mui/icons-material/Visibility"
import { useState } from "react"
import ComposerPage from "./composerpage"
import ViewerPage from "./viewerpage"
import IconButton from "@mui/material/IconButton"
import Tooltip from "@mui/material/Tooltip"

export default function PageSwitcher() {
  const [page, setPage] = useState<"composer" | "viewer">("composer")

  return (
    <div className="pageswitcher-root">
      <nav className="pageswitcher-sidebar">
        <Tooltip title="Composer" placement="right" enterDelay={1000} enterNextDelay={1000}>
          <IconButton
            className={`pageswitcher-icon-btn${page === "composer" ? " active" : ""}`}
            onClick={() => setPage("composer")}
            aria-label="Composer"
            size="large"
          >
            <BuildIcon fontSize="large" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Viewer" placement="right" enterDelay={1000} enterNextDelay={1000}>
          <IconButton
            className={`pageswitcher-icon-btn${page === "viewer" ? " active" : ""}`}
            onClick={() => setPage("viewer")}
            aria-label="Viewer"
            size="large"
          >
            <VisibilityIcon fontSize="large" />
          </IconButton>
        </Tooltip>
      </nav>
      <main className="pageswitcher-content">
        {page === "composer" ? <ComposerPage /> : <ViewerPage />}
      </main>
    </div>
  )
}