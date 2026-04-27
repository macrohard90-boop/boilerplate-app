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

// 50 real-sounding names — each user gets a unique first+last combo
const FIRST_NAMES = [
  "Emma", "Liam", "Olivia", "Noah", "Ava",
  "James", "Sophia", "Lucas", "Mia", "Ethan",
  "Isabella", "Mason", "Charlotte", "Logan", "Amelia",
  "Alexander", "Harper", "Benjamin", "Evelyn", "Daniel",
  "Aria", "Henry", "Ella", "Sebastian", "Scarlett",
  "Jack", "Grace", "Owen", "Chloe", "Samuel",
  "Lily", "Ryan", "Zoey", "Nathan", "Penelope",
  "Leo", "Layla", "Isaac", "Riley", "Caleb",
  "Nora", "Luke", "Hannah", "Aaron", "Stella",
  "Dylan", "Maya", "Gabriel", "Aurora", "Julian",
];

const LAST_NAMES = [
  "Anderson", "Martinez", "Thompson", "Garcia", "Robinson",
  "Clark", "Rodriguez", "Lewis", "Walker", "Hall",
  "Young", "King", "Wright", "Lopez", "Hill",
  "Scott", "Green", "Adams", "Baker", "Nelson",
  "Carter", "Mitchell", "Perez", "Roberts", "Turner",
  "Phillips", "Campbell", "Parker", "Evans", "Edwards",
  "Collins", "Stewart", "Morris", "Reed", "Morgan",
  "Cooper", "Howard", "Ward", "Torres", "Peterson",
  "Gray", "Watson", "Brooks", "Kelly", "Sanders",
  "Price", "Bennett", "Wood", "Barnes", "Ross",
];

interface PersonaDef {
  tag: string;
  count: number;
}

const PERSONA_DEFS: Record<string, PersonaDef> = {
  window_shopper: { tag: "shopper", count: 15 },
  cart_abandoner: { tag: "abandoner", count: 10 },
  single_buyer: { tag: "buyer", count: 12 },
  power_buyer: { tag: "power", count: 5 },
  subscriber: { tag: "sub", count: 5 },
  bouncer: { tag: "bounce", count: 3 },
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
      firstName: FIRST_NAMES[(_globalIndex - 1) % FIRST_NAMES.length],
      lastName: LAST_NAMES[(_globalIndex - 1) % LAST_NAMES.length],
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
