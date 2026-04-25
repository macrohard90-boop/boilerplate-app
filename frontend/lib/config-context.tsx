"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

interface AppConfig {
  enable_products: boolean;
  enable_subscriptions: boolean;
  enable_coupons: boolean;
  enable_tracking: boolean;
  enable_seo_scoring: boolean;
  enable_seo_crawler: boolean;
  enable_seo_keywords: boolean;
  enable_geo_scoring: boolean;
  enable_seo_advisor: boolean;
  enable_geo_advisor: boolean;
  enable_marketing: boolean;
  enable_marketing_emails: boolean;
  enable_sms: boolean;
  enable_whatsapp: boolean;
  site_name: string;
  site_description: string;
}

const DEFAULT_CONFIG: AppConfig = {
  enable_products: true,
  enable_subscriptions: true,
  enable_coupons: true,
  enable_tracking: true,
  enable_seo_scoring: true,
  enable_seo_crawler: false,
  enable_seo_keywords: true,
  enable_geo_scoring: true,
  enable_seo_advisor: true,
  enable_geo_advisor: true,
  enable_marketing: true,
  enable_marketing_emails: true,
  enable_sms: false,
  enable_whatsapp: false,
  site_name: "Boilerplate App",
  site_description: "",
};

const ConfigContext = createContext<AppConfig>(DEFAULT_CONFIG);

export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<AppConfig>(DEFAULT_CONFIG);

  useEffect(() => {
    fetch("/api/config")
      .then((r) => (r.ok ? r.json() : DEFAULT_CONFIG))
      .then(setConfig)
      .catch(() => {});
  }, []);

  return (
    <ConfigContext.Provider value={config}>{children}</ConfigContext.Provider>
  );
}

export function useConfig() {
  return useContext(ConfigContext);
}
