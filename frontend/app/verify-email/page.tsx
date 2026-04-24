import { Suspense } from "react";
import VerifyEmailContent from "./VerifyEmailContent";

export default function VerifyEmailPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <Suspense
        fallback={
          <div className="glass rounded-2xl p-8 max-w-md w-full text-center space-y-6">
            <div className="w-12 h-12 rounded-full border-2 border-accent-blue border-t-transparent animate-spin mx-auto" />
            <p className="text-text-secondary">Verifying your email...</p>
          </div>
        }
      >
        <VerifyEmailContent />
      </Suspense>
    </div>
  );
}
