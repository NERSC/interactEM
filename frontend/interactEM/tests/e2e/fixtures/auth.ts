import { expect, test as base, type Page } from "@playwright/test"

const username = process.env.FIRST_SUPERUSER_USERNAME
const password = process.env.FIRST_SUPERUSER_PASSWORD

async function login(page: Page) {
  if (!username || !password) {
    throw new Error(
      "FIRST_SUPERUSER_USERNAME and FIRST_SUPERUSER_PASSWORD must be set for Playwright tests",
    )
  }

  await page.goto("/", { waitUntil: "domcontentloaded" })
  await page.waitForSelector("text=Login")
  await page.getByLabel("Username").fill(username)
  await page.getByLabel("Password").fill(password)
  await page.getByRole("button", { name: /login/i }).click()
  await page.waitForSelector(".composer-page", { timeout: 20_000 })
  await expect(page.locator(".composer-page")).toBeVisible()
}

type Fixtures = {
  authPage: Page
}

export const test = base.extend<Fixtures>({
  authPage: async ({ page }, use) => {
    await login(page)
    await use(page)
  },
})

export { expect } from "@playwright/test"
