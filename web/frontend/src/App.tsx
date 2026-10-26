import { Navigate, Route, Routes } from "react-router-dom";
import { StyleGuidePage } from "./app/styleguide/StyleGuidePage";

export function App() {
  return (
    <Routes>
      <Route path="/styleguide" element={<StyleGuidePage />} />
      <Route path="*" element={<Navigate to="/styleguide" replace />} />
    </Routes>
  );
}