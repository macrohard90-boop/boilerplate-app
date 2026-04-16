"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function SeoRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/admin/seo/discover");
  }, [router]);
  return null;
}
