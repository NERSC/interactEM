import { useState } from "react"
import ComposerPage from "./composerpage"
import ViewerPage from "./viewerpage"

export default function PageSwitcher() {
  const [page, setPage] = useState<"composer" | "viewer">("composer")

  return (
    <div className="pageswitcher-root">
      <main className="pageswitcher-content">
        {page === "composer" ? <ComposerPage /> : <ViewerPage />}
      </main>
    </div>
  )
}
