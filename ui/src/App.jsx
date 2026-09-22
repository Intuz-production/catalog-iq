import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./components/auth/auth-provider";
import { ToastProvider } from "./components/toast-provider";
import { ConfirmProvider } from "./components/confirm-provider";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/auth/protected-route";
import Dashboard from "./pages/Dashboard";
import Products from "./pages/Products";
import Ingestion from "./pages/Ingestion";
import Competitors from "./pages/Competitors";
import Login from "./pages/Login";

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
      <ConfirmProvider>
        
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/products" element={<Ingestion />} />
              <Route path="/products/:jobId" element={<Products />} />
              <Route path="/ingestion" element={<Navigate to="/products" replace />} />
              <Route path="/content" element={<Navigate to="/products" replace />} />
              <Route path="/competitors" element={<Competitors />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
      </ConfirmProvider>
      </ToastProvider>
    </AuthProvider>
  );
}
