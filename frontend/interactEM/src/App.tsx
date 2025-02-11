import { Flip, ToastContainer } from "react-toastify"
import InteractEM from "./pages/interactem"

export default function App() {
  return (
    <>
      <InteractEM authMode="internal" />
      <ToastContainer
        position="top-left"
        autoClose={5000}
        hideProgressBar={false}
        newestOnTop
        closeOnClick
        pauseOnFocusLoss
        draggable
        pauseOnHover
        transition={Flip}
      />
    </>
  )
}
