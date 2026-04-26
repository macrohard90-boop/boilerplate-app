import type { Metadata } from "next";
import { AuthProvider } from "../lib/auth-context";
import { CartProvider } from "../lib/cart-context";
import { ConfigProvider } from "../lib/config-context";
import { ToastProvider } from "../components/Toast";
import Header from "../components/Header";
import Footer from "../components/Footer";
import ConditionalDurationTracker from "../components/ConditionalDurationTracker";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Boilerplate App",
    template: "%s | Boilerplate App",
  },
  description: "A modern e-commerce platform",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000",
  ),
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=JetBrains+Mono:wght@400;500&family=Outfit:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen flex flex-col">
        <ConfigProvider>
          <AuthProvider>
            <CartProvider>
              <ToastProvider>
                <Header />
                <main className="flex-1 pt-16">{children}</main>
                <Footer />
                <ConditionalDurationTracker />
              </ToastProvider>
            </CartProvider>
          </AuthProvider>
        </ConfigProvider>
      </body>
    </html>
  );
}
