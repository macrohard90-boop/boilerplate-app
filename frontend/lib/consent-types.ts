export interface ConsentType {
  key: string;
  label: string;
  description: string;
  category: "email" | "data" | "analytics" | "cookies";
  defaultValue: boolean;
  required?: boolean;
}

export const CONSENT_TYPES: ConsentType[] = [
  {
    key: "transactional_email",
    label: "Transactional Emails",
    description:
      "Order confirmations, password resets, and account notifications",
    category: "email",
    defaultValue: true,
    required: true,
  },
  {
    key: "marketing_email",
    label: "Marketing Emails",
    description: "Promotional emails, newsletters, and special offers",
    category: "email",
    defaultValue: false,
  },
  {
    key: "third_party_sharing",
    label: "Third-Party Sharing",
    description: "Share data with trusted third-party partners",
    category: "data",
    defaultValue: false,
  },
  {
    key: "analytics",
    label: "Web Analytics",
    description: "Help us understand how you use the site to improve it",
    category: "analytics",
    defaultValue: false,
  },
  {
    key: "cookies_analytics",
    label: "Analytics Cookies",
    description: "Cookies that help us measure site usage and performance",
    category: "cookies",
    defaultValue: false,
  },
  {
    key: "cookies_marketing",
    label: "Marketing Cookies",
    description: "Cookies used for personalized ads and promotions",
    category: "cookies",
    defaultValue: false,
  },
];

export const CATEGORY_LABELS: Record<string, string> = {
  email: "Email Preferences",
  data: "Data Sharing",
  analytics: "Analytics",
  cookies: "Cookie Preferences",
};

/** Maps consent record keys to cookie preference keys for syncing */
export const CONSENT_TO_COOKIE_MAP: Record<string, string> = {
  cookies_analytics: "analytics",
  cookies_marketing: "marketing",
};
