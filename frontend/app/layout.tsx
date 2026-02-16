import type { Metadata } from "next";
import { AuthProvider } from "../lib/auth-context";
import AuthNav from "../components/AuthNav";

export const metadata: Metadata = {
  title: "Boilerplate App",
  description: "Boilerplate application - ready for customization",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ margin: 0 }}>
        <AuthProvider>
          <AuthNav />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
