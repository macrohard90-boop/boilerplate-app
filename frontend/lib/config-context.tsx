"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

interface AppConfig {
  enable_products: boolean;
  enable_subscriptions: boolean;
  enable_coupons: boolean;
  enable_tracking: boolean;
}

const DEFAULT_CONFIG: AppConfig = {
  enable_products: true,
  enable_subscriptions: true,
  enable_coupons: true,
  enable_tracking: true,
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
