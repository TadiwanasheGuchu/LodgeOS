import { expect, test, type Page } from "@playwright/test";
import { seed, signedIn } from "./fixtures";

test.describe.configure({ mode: "serial" });

// Created by properties.spec.ts, which runs before this file.
const propertyName = `Waterberg Lodge ${seed.run}`;

async function openRates(page: Page) {
  await page.goto("/properties");
  await page.getByRole("link", { name: new RegExp(propertyName) }).click();
  await page.getByRole("link", { name: "Rates" }).click();
  await expect(page.getByRole("link", { name: "Rates" })).toHaveAttribute("aria-current", "page");
}

test("owner sets taxes, a rate plan, prices and a season, then prices a stay", async ({ page }) => {
  await signedIn(page, seed.owner);
  await openRates(page);

  for (const [name, rate] of [["VAT", "15"], ["Tourism levy", "1"]]) {
    await page.getByRole("button", { name: "Add tax" }).click();
    const d = page.getByRole("dialog");
    await d.getByLabel("Name").fill(name);
    await d.getByLabel("Rate (%)").fill(rate);
    await d.getByRole("button", { name: "Add tax" }).click();
    await expect(page.getByText(`${rate}%`, { exact: true })).toBeVisible();
  }

  await page.getByRole("button", { name: "Add rate plan" }).click();
  let d = page.getByRole("dialog");
  await d.getByLabel("Name").fill("Bed and breakfast");
  await d.getByLabel("Code").fill("bb");
  await d.getByLabel("Meals included").selectOption("bed_and_breakfast");
  await d.getByRole("button", { name: "Add rate plan" }).click();
  await expect(page.getByRole("heading", { name: /Bed and breakfast/ })).toBeVisible();
  await expect(page.getByText("No price set: this room type cannot be quoted")).toBeVisible();

  await page.getByRole("button", { name: "Set prices for Chalet" }).click();
  d = page.getByRole("dialog");
  await d.getByLabel("Per night").fill("1 000");
  await d.getByLabel(/Weekend night/).fill("1200");
  await d.getByLabel("Extra adult").fill("300");
  await d.getByRole("button", { name: "Save prices" }).click();
  await expect(page.getByRole("cell", { name: "NAD 1 000.00" })).toBeVisible();

  await page.getByRole("button", { name: "Add season" }).click();
  d = page.getByRole("dialog");
  await d.getByLabel("Name").fill("Festive");
  await d.getByLabel("First night").fill("2026-12-20");
  await d.getByLabel("Last night").fill("2027-01-05");
  await d.getByLabel("Per night").fill("1500");
  await d.getByRole("button", { name: "Add season" }).click();
  await expect(page.getByText(/20 Dec 2026 to 5 Jan 2027/)).toBeVisible();

  // An overlapping season is refused with an explanation.
  await page.getByRole("button", { name: "Add season" }).click();
  d = page.getByRole("dialog");
  await d.getByLabel("Name").fill("New Year");
  await d.getByLabel("First night").fill("2026-12-31");
  await d.getByLabel("Last night").fill("2027-01-02");
  await d.getByLabel("Per night").fill("1800");
  await d.getByRole("button", { name: "Add season" }).click();
  await expect(d.getByText("These dates overlap another season for this room type in this rate plan.")).toBeVisible();
  await page.keyboard.press("Escape");

  // Fri 18 and Sat 19 Dec are weekend nights (1200), 20 and 21 Dec are festive (1500).
  const quote = page.getByRole("region", { name: "Price a stay" }).or(page.locator("section", { has: page.getByRole("heading", { name: "Price a stay" }) }));
  await quote.getByLabel("Arrival").fill("2026-12-18");
  await quote.getByLabel("Departure").fill("2026-12-22");
  await quote.getByRole("button", { name: "Calculate" }).click();
  await expect(quote.getByText("Fri 18 Dec · weekend")).toBeVisible();
  await expect(quote.getByText("Sun 20 Dec · Festive")).toBeVisible();
  await expect(quote.getByText("NAD 5 400.00")).toBeVisible();
  await expect(quote.getByText("VAT (15%)")).toBeVisible();

  // Rules are explained, not hidden.
  await quote.getByLabel("Adults").fill("9");
  await quote.getByRole("button", { name: "Calculate" }).click();
  await expect(quote.getByText(/takes at most/)).toBeVisible();
});

test("receptionist can price a stay but not change rates", async ({ page }) => {
  await signedIn(page, seed.receptionist);
  await openRates(page);
  await expect(page.getByRole("heading", { name: /Bed and breakfast/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Add tax" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add rate plan" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Set prices/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Calculate" })).toBeVisible();
});
