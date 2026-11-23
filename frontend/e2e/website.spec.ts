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

test("staff share a guest link; the guest sends arrival details and asks to cancel", async ({ page }) => {
  await signedIn(page, seed.receptionist);
  await page.goto("/reservations");
  await page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName }).click();
  await expect(page.getByText(new RegExp(`^${propertyName} · stays from`))).toBeVisible();
  await page.getByRole("link", { name: "New booking" }).click();
  await expect(page.getByText(propertyName, { exact: true })).toBeVisible();
  await page.getByLabel("Arrival").fill("2027-10-05");
  await page.getByLabel("Departure").fill("2027-10-07");
  await page.getByRole("button", { name: "Add a Chalet" }).click();
  await page.getByLabel("First name").fill("Tangeni");
  await page.getByLabel("Last name").fill(`Haufiku ${seed.run}`);
  await page.getByRole("button", { name: /^Book/ }).click();
  await expect(page.getByRole("heading", { name: /^LOS-/ })).toBeVisible();
  const booking = page.url();

  await page.getByRole("button", { name: "Share guest link" }).click();
  const link = (await page.locator("code").filter({ hasText: "/stay/" }).textContent())!;
  await expect(page.getByRole("link", { name: "WhatsApp" })).toHaveAttribute("href", /^https:\/\/wa\.me\/\?text=/);

  await page.context().clearCookies();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(new URL(link).pathname);
  await expect(page.getByRole("region", { name: "Booking" })).toContainText(`Booking for Tangeni Haufiku ${seed.run}`);
  await page.getByLabel("Expected arrival time").fill("20:30");
  await page.getByLabel("Message to the property (optional)").fill("Driving from Windhoek");
  await page.getByRole("button", { name: "Send to the property" }).click();
  await expect(page.getByText("Thank you. The property has your details.")).toBeVisible();
  await page.getByRole("button", { name: "Need to cancel?" }).click();
  await page.getByLabel("Reason").fill("Change of plans");
  await page.getByRole("button", { name: "Ask to cancel" }).click();
  await expect(page.getByText("You asked to cancel (Change of plans).")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await page.setViewportSize({ width: 1280, height: 900 });
  await signedIn(page, seed.receptionist);
  await page.goto(booking);
  await expect(page.getByText("Arriving around 20:30")).toBeVisible();
  await expect(page.getByText("Driving from Windhoek")).toBeVisible();
  const banner = page.getByRole("alert").filter({ hasText: "The guest asked to cancel" });
  await expect(banner).toContainText("Change of plans");
  await banner.getByRole("button", { name: "Keep the booking" }).click();
  await expect(page.getByText("The guest asked to cancel")).toHaveCount(0);

  // A withdrawn link stops working.
  await page.getByRole("button", { name: "Withdraw all guest links" }).click();
  await expect(page.getByText("Withdrew 1 link.")).toBeVisible();
  await page.goto(new URL(link).pathname);
  await expect(page.getByText("This link has expired or was withdrawn. Please contact the property.")).toBeVisible();
});
