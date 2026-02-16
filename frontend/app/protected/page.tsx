"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../lib/auth-context";

export default function ProtectedPage() {
  const router = useRouter();
  const { user, session, activeSessionsCount, isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div style={{ padding: 40, textAlign: "center", fontFamily: "system-ui, sans-serif" }}>
        Loading...
      </div>
    );
  }

  if (!user) return null;

  return (
    <div style={{ maxWidth: 600, margin: "40px auto", fontFamily: "system-ui, sans-serif" }}>
      <div
        style={{
          background: "#dcfce7",
          border: "2px solid #16a34a",
          padding: 16,
          borderRadius: 8,
          textAlign: "center",
          marginBottom: 32,
          fontWeight: 700,
          color: "#16a34a",
        }}
      >
        This page proves auth works
      </div>

      <h1 style={{ marginBottom: 24 }}>Protected Dashboard</h1>

      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 18, marginBottom: 8, borderBottom: "1px solid #eee", paddingBottom: 4 }}>
          User Info
        </h2>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <tbody>
            {([
              ["Email", user.email],
              ["Name", `${user.first_name || ""} ${user.last_name || ""}`.trim() || "N/A"],
              ["Role", user.role],
              ["Verified", user.is_verified ? "Yes" : "No"],
              ["Created", new Date(user.created_at).toLocaleString()],
            ] as [string, string][]).map(([label, value]) => (
              <tr key={label}>
                <td style={{ padding: "6px 8px", fontWeight: 500, color: "#666", width: "30%" }}>{label}</td>
                <td style={{ padding: "6px 8px" }}>{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {session && (
        <section style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 18, marginBottom: 8, borderBottom: "1px solid #eee", paddingBottom: 4 }}>
            Session Info
          </h2>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              {([
                ["Session ID", session.session_id],
                ["Device", session.device || "N/A"],
                ["IP Address", session.ip_address || "N/A"],
                ["Created", new Date(session.created_at).toLocaleString()],
                ["Active Sessions", String(activeSessionsCount)],
              ] as [string, string][]).map(([label, value]) => (
                <tr key={label}>
                  <td style={{ padding: "6px 8px", fontWeight: 500, color: "#666", width: "30%" }}>{label}</td>
                  <td style={{ padding: "6px 8px", wordBreak: "break-all" }}>{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section>
        <h2 style={{ fontSize: 18, marginBottom: 8, borderBottom: "1px solid #eee", paddingBottom: 4 }}>
          Permissions ({user.permissions.length})
        </h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {user.permissions.map((p) => (
            <span
              key={p}
              style={{
                background: "#f3f4f6",
                padding: "4px 10px",
                borderRadius: 4,
                fontSize: 13,
                fontFamily: "monospace",
              }}
            >
              {p}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
