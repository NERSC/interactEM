import { expect } from "@playwright/test"
import { test } from "./fixtures/auth"

test("loads composer page", async ({ authPage }) => {
  await authPage.waitForSelector(".composer-page", { timeout: 20_000 })
  await expect(authPage.locator(".composer-page")).toBeVisible()
})
