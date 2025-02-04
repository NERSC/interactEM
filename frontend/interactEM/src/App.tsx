import { ToastContainer } from "react-toastify"
import InteractEM from "./pages/interactem"

export default function App() {
  return (
    <>
      <InteractEM authMode="internal" />
      <ToastContainer
        position="top-right"
        autoClose={5000}
        hideProgressBar={false}
        newestOnTop
        closeOnClick
        pauseOnFocusLoss
        draggable
        pauseOnHover
      />
    </>
  )
}
