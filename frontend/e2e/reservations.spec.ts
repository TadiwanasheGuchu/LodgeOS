import { expect, test } from "@playwright/test";
import { seed, signedIn } from "./fixtures";

test.describe.configure({ mode: "serial" });

// Waterberg (6 chalets) and its "Bed and breakfast" plan come from properties.spec.ts and
// rates.spec.ts, which run before this file.
const propertyName = `Waterberg Lodge ${seed.run}`;

test("receptionist takes a phone booking, then cancels it with a reason", async ({ page }) => {
  await signedIn(page, seed.receptionist);
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Reservations" }).click();
  await page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName }).click();
  await expect(page.getByText(new RegExp(`^${propertyName} · stays from`))).toBeVisible();
  await page.getByRole("link", { name: "New booking" }).click();
  await expect(page.getByText(propertyName, { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "New booking" })).toBeVisible();

  // Friday 5 and Saturday 6 March 2027 are weekend nights: 1200.00 each.
  await page.getByLabel("Arrival").fill("2027-03-05");
  await page.getByLabel("Departure").fill("2027-03-07");
  await expect(page.getByText("2 nights")).toBeVisible();
  await expect(page.getByText("6 free")).toBeVisible();
  await page.getByRole("button", { name: "Add a Chalet" }).click();
  await expect(page.getByText("NAD 2 400.00").first()).toBeVisible();
  await expect(page.getByText("5 free")).toBeVisible();

  await page.getByRole("button", { name: /^Book/ }).click();
  await expect(page.getByText("Choose a returning guest or enter the guest's first and last name.")).toBeVisible();
  await page.getByLabel("First name").fill("Iyaloo");
  await page.getByLabel("Last name").fill(`Shilongo ${seed.run}`);
  await page.getByLabel("Email (optional)").fill(`iyaloo-${seed.run}@example.com`);
  await page.getByRole("button", { name: /^Book/ }).click();

  await expect(page.getByRole("heading", { name: /^LOS-[A-Z2-9]{6}/ })).toBeVisible();
  await expect(page.getByText("Confirmed", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Room not assigned yet")).toBeVisible();
  await expect(page.getByText("Fri 5 Mar · weekend")).toBeVisible();
  await expect(page.getByText("NAD 2 400.00").last()).toBeVisible();

  await page.getByRole("button", { name: "Cancel booking" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Cancel booking" }).click();
  await expect(dialog.getByText("Give a reason for the cancellation.")).toBeVisible();
  await dialog.getByLabel("Reason").fill("Guest changed travel plans");
  await dialog.getByRole("button", { name: "Cancel booking" }).click();
  await expect(page.getByText("Cancelled: Guest changed travel plans")).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel booking" })).toHaveCount(0);
});

test("a returning guest can be found when booking", async ({ page }) => {
  await signedIn(page, seed.receptionist);
  await page.goto("/reservations");
  await page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName }).click();
  await expect(page.getByText(new RegExp(`^${propertyName} · stays from`))).toBeVisible();
  await page.getByRole("link", { name: "New booking" }).click();
  await expect(page.getByText(propertyName, { exact: true })).toBeVisible();
  await page.getByLabel("Returning guest").fill(`Shilongo ${seed.run}`);
  await page.getByRole("button", { name: new RegExp(`Iyaloo Shilongo ${seed.run}`) }).click();
  await expect(page.getByRole("button", { name: "Change" })).toBeVisible();
});

test("housekeeping does not see reservations or guest details", async ({ page }) => {
  await signedIn(page, seed.housekeeping);
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Reservations" })).toHaveCount(0);
  await page.goto("/reservations");
  await expect(page).toHaveURL(/\/$/);
});
