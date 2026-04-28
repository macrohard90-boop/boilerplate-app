/**
 * Global setup — runs once before all tests.
 * Verifies the target server is reachable before starting the test suite.
 */

const BASE_URL = process.env.BASE_URL || "http://34.30.88.59";
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 5000;

async function healthCheck(): Promise<void> {
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);
      const res = await fetch(`${BASE_URL}/api/ecommerce/products?page=1&page_size=1`, {
        signal: controller.signal,
      });
      clearTimeout(timeout);

      if (res.ok) {
        console.log(`  Health check passed (attempt ${attempt}): ${BASE_URL} is reachable`);
        return;
      }
      console.warn(`  Health check attempt ${attempt}: HTTP ${res.status}`);
    } catch (err) {
      console.warn(`  Health check attempt ${attempt}: ${(err as Error).message}`);
    }

    if (attempt < MAX_RETRIES) {
      console.log(`  Retrying in ${RETRY_DELAY_MS / 1000}s...`);
      await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
    }
  }

  throw new Error(
    `Server at ${BASE_URL} is not reachable after ${MAX_RETRIES} attempts. ` +
      `Aborting test suite. Check that the VM is running.`,
  );
}

export default healthCheck;
