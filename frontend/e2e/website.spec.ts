import { expect, test } from "@playwright/test";
import { seed, signedIn } from "./fixtures";

// Runs last among desktop specs: Waterberg has chalets, rates and taxes set up.
const propertyName = `Waterberg Lodge ${seed.run}`;

test("owner opens online booking; a guest books from a phone", async ({ page }) => {
  await signedIn(page, seed.owner);
  await page.goto("/properties");
  await page.getByRole("link", { name: propertyName }).first().click();
  await page.getByRole("navigation", { name: "Property sections" }).getByRole("link", { name: "Online booking" }).click();

  // Terms are required before going live.
  await page.getByLabel("Take bookings online").check();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Add booking terms (cancellation and payment policy) before taking bookings online.")).toBeVisible();
  await page.getByRole("region", { name: "Rates sold online" }).getByRole("listitem").filter({ hasText: "Bed and breakfast" }).getByLabel("Sell online").check();
  await expect(page.getByText(/1 rate offered/)).toBeVisible();
  await page.getByLabel("Booking terms").fill("Free cancellation up to 7 days before arrival.\nPay on arrival by card or cash.");
  await page.getByLabel("About the property (optional)").fill("Chalets on the Waterberg plateau.");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved. Guests can book online.")).toBeVisible();
  const url = (await page.locator("code").textContent())!;
  expect(url).toMatch(/\/book\/[a-z0-9-]+\/[a-z0-9-]+$/);

  // An anonymous guest on a phone.
  await page.context().clearCookies();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(new URL(url).pathname);
  await expect(page.getByText("Chalets on the Waterberg plateau.")).toBeVisible();
  await page.getByLabel("Arrival").fill("2027-08-10");
  await page.getByLabel("Departure").fill("2027-08-12");
  await page.getByRole("button", { name: "Check availability" }).click();
  const chalet = page.getByRole("article", { name: "Chalet" });
  await expect(chalet).toContainText("Bed and breakfast");
  await expect(chalet).toContainText("2 nights, taxes included");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await chalet.getByRole("button", { name: "Book" }).first().click();

  await page.getByLabel("First name").fill("Hileni");
  await page.getByLabel("Last name").fill(`Shapwa ${seed.run}`);
  await page.getByLabel("Email").fill(`hileni-${seed.run}@example.com`);
  await page.getByLabel("Special requests (optional)").fill("Arriving after dark");
  await page.getByRole("button", { name: "Send booking request" }).click();
  await expect(page.getByText("Please read and accept the booking terms.")).toBeVisible();
  await page.getByLabel("I accept the booking terms").check();
  await page.getByRole("button", { name: "Send booking request" }).click();

  const done = page.getByRole("region", { name: "Booking received" });
  await expect(done).toContainText("Request received");
  await expect(done).toContainText(`Thank you, Hileni Shapwa ${seed.run}`);
  await expect(done.getByText(/^LOS-[A-Z0-9]{6}$/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  // A property that is not live is not found.
  await page.goto("/book/no-such-org/no-such-property");
  await expect(page.getByText(/not found|could not be found/i).first()).toBeVisible();
});
