import { expect, test } from "@playwright/test";
import { seed, signIn } from "./fixtures";

test("phone layout uses a menu and has no horizontal scroll", async ({ page }) => {
  await signIn(page, seed.owner);
  await expect(page.getByRole("heading", { name: /Hello, Olivia/ })).toBeVisible();

  const menu = page.getByRole("button", { name: "Open menu" });
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await menu.click();
  await page.locator("#mobile-nav").getByRole("link", { name: "Team" }).click();
  await expect(page.getByRole("heading", { name: "Team" })).toBeVisible();
  await expect(page.locator("#mobile-nav")).toHaveCount(0); // closed after navigating

  for (const path of ["/", "/team", "/activity", "/settings"]) {
    await page.goto(path);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `horizontal overflow on ${path}`).toBeLessThanOrEqual(0);
  }
});
