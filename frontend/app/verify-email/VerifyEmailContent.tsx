"use client";

import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "../../lib/api";

export default function VerifyEmailContent() {
  const params = useSearchParams();
  const token = params.get("token");

  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading",
  );
  const [message, setMessage] = useState("");
  const called = useRef(false);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("No verification token provided.");
      return;
    }

    if (called.current) return;
    called.current = true;

    apiFetch<{ message: string }>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    })
      .then((res) => {
        setStatus("success");
        setMessage(res.message || "Email verified successfully!");
      })
      .catch((err: unknown) => {
        setStatus("error");
        const msg =
          err && typeof err === "object" && "message" in err
            ? (err as { message: string }).message
            : "Invalid or expired verification token.";
        setMessage(msg);
      });
  }, [token]);

  return (
    <div className="glass rounded-2xl p-8 max-w-md w-full text-center space-y-6">
      {status === "loading" && (
        <>
          <div className="w-12 h-12 rounded-full border-2 border-accent-blue border-t-transparent animate-spin mx-auto" />
          <p className="text-text-secondary">Verifying your email...</p>
        </>
      )}

      {status === "success" && (
        <>
          <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto">
            <span className="text-3xl text-green-400">&#10003;</span>
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            Email Verified
          </h1>
          <p className="text-text-secondary">{message}</p>
          <Link
            href="/auth/login"
            className="inline-block px-6 py-2.5 rounded-lg bg-accent-blue text-white font-medium hover:bg-accent-blue/80 transition-colors"
          >
            Continue to Login
          </Link>
        </>
      )}

      {status === "error" && (
        <>
          <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mx-auto">
            <span className="text-3xl text-red-400">&#10007;</span>
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            Verification Failed
          </h1>
          <p className="text-text-secondary">{message}</p>
          <p className="text-sm text-text-muted">
            The link may have expired (valid for 24 hours). Contact support or
            request a new verification email.
          </p>
          <Link
            href="/auth/login"
            className="inline-block px-6 py-2.5 rounded-lg bg-glass-bg border border-glass-border text-text-primary font-medium hover:bg-glass-hover transition-colors"
          >
            Back to Login
          </Link>
        </>
      )}
    </div>
  );
}
