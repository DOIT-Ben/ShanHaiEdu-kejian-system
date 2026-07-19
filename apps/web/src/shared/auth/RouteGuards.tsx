import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useMockSession } from "@/shared/auth/mockAuth";

export function RequireSession() {
  const session = useMockSession();
  const location = useLocation();
  if (!session) {
    return <Navigate replace state={{ from: location }} to="/login" />;
  }
  return <Outlet />;
}

export function RequireAdmin() {
  const session = useMockSession();
  const location = useLocation();
  if (!session) {
    return <Navigate replace state={{ from: location }} to="/login" />;
  }
  if (session.user.role !== "admin") {
    return <Navigate replace to="/app" />;
  }
  return <Outlet />;
}
