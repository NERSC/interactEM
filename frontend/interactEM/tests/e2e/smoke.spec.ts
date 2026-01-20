import { expect } from "@playwright/test"
import { NATS_STATUS_TOOLTIPS } from "../../src/components/natsstatus"
import { test } from "./fixtures/auth"

test("loads composer page", async ({ authPage }) => {
  await authPage.waitForSelector(".composer-page", { timeout: 20_000 })
  await expect(authPage.locator(".composer-page")).toBeVisible()
})

test("shows NATS connected after login", async ({ authPage }) => {
  const natsChip = authPage
    .locator(".composer-page")
    .getByText("NATS", { exact: true })

  await expect(natsChip).toBeVisible()
  await natsChip.hover()
  await expect(authPage.getByRole("tooltip")).toHaveText(
    NATS_STATUS_TOOLTIPS.connected,
    { timeout: 5_000 },
  )
})
