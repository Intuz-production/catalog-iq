import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Products from "./pages/Products";
import Ingestion from "./pages/Ingestion";
import ContentGen from "./pages/ContentGen";
import Competitors from "./pages/Competitors";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/products" element={<Products />} />
          <Route path="/ingestion" element={<Ingestion />} />
          <Route path="/content" element={<ContentGen />} />
          <Route path="/competitors" element={<Competitors />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
