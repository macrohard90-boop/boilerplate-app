/**
 * 100 test users distributed across 6 personas and 6 device profiles.
 * Each user gets a unique email, a persona assignment, and a device profile (round-robin).
 */

export interface DeviceProfile {
  name: string;
  viewport: { width: number; height: number };
  isMobile: boolean;
  hasTouch: boolean;
  userAgent?: string;
}

export interface TestUser {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
  persona: string;
  device: DeviceProfile;
  index: number;
}

export const DEVICES: DeviceProfile[] = [
  {
    name: "Desktop Chrome",
    viewport: { width: 1280, height: 720 },
    isMobile: false,
    hasTouch: false,
  },
  {
    name: "Desktop Large",
    viewport: { width: 1920, height: 1080 },
    isMobile: false,
    hasTouch: false,
  },
  {
    name: "iPhone 13",
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    userAgent:
      "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
  },
  {
    name: "Pixel 7",
    viewport: { width: 412, height: 915 },
    isMobile: true,
    hasTouch: true,
    userAgent:
      "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
  },
  {
    name: "iPad Pro",
    viewport: { width: 1024, height: 1366 },
    isMobile: false,
    hasTouch: true,
    userAgent:
      "Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
  },
  {
    name: "Mobile Landscape",
    viewport: { width: 844, height: 390 },
    isMobile: true,
    hasTouch: true,
  },
];

const PASSWORD = "TestPass1!";

interface PersonaDef {
  tag: string;
  firstName: string;
  count: number;
}

const PERSONA_DEFS: Record<string, PersonaDef> = {
  window_shopper: { tag: "shopper", firstName: "Shopper", count: 15 },
  cart_abandoner: { tag: "abandoner", firstName: "Abandoner", count: 10 },
  single_buyer: { tag: "buyer", firstName: "Buyer", count: 12 },
  power_buyer: { tag: "power", firstName: "Power", count: 5 },
  subscriber: { tag: "sub", firstName: "Subscriber", count: 5 },
  bouncer: { tag: "bounce", firstName: "Bounce", count: 3 },
};

/** Global counter across all personas so emails are sequential: test001, test002, ... */
let _globalIndex = 0;

function generatePersonaUsers(
  persona: string,
  def: PersonaDef,
): TestUser[] {
  const users: TestUser[] = [];
  for (let i = 1; i <= def.count; i++) {
    _globalIndex++;
    const padded = String(_globalIndex).padStart(3, "0");
    users.push({
      email: `adrian+test${padded}@estmgroup.com`,
      password: PASSWORD,
      firstName: def.firstName,
      lastName: `${def.tag}${String(i).padStart(2, "0")}`,
      persona,
      device: DEVICES[(i - 1) % DEVICES.length],
      index: i,
    });
  }
  return users;
}

/** All 50 users. */
let _allUsers: TestUser[] | null = null;
export function getAllUsers(): TestUser[] {
  if (!_allUsers) {
    _allUsers = [];
    for (const [persona, def] of Object.entries(PERSONA_DEFS)) {
      _allUsers.push(...generatePersonaUsers(persona, def));
    }
  }
  return _allUsers;
}

/** Get users for a specific persona. */
export function getUsersByPersona(persona: string): TestUser[] {
  return getAllUsers().filter((u) => u.persona === persona);
}

/** Subset for cross-browser projects: first 2 users per persona. */
export function getCrossBrowserSubset(): TestUser[] {
  const subset: TestUser[] = [];
  for (const persona of Object.keys(PERSONA_DEFS)) {
    subset.push(...getUsersByPersona(persona).slice(0, 2));
  }
  return subset;
}

/** Auth state file path for a user. */
export function authStatePath(email: string): string {
  const safe = email.replace(/@/g, "_at_").replace(/\./g, "_");
  return `auth-states/${safe}.json`;
}
