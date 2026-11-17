import { expect, test } from "@playwright/test";
import { seed, signedIn } from "./fixtures";

// Runs after properties, rates and reservations specs, which set up Waterberg with chalets
// 1-6 and a "Bed and breakfast" plan.
const propertyName = `Waterberg Lodge ${seed.run}`;
const guestLast = `Hamutenya ${seed.run}`;

test("book, assign a room, and see the stay on the calendar", async ({ page }) => {
  await signedIn(page, seed.receptionist);

  // The overview shows today's movements for front-desk roles.
  await expect(page.getByText(`Today at ${propertyName}`)).toBeVisible();

  await page.goto("/reservations");
  await page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName }).click();
  await expect(page.getByText(new RegExp(`^${propertyName} · stays from`))).toBeVisible();
  await page.getByRole("link", { name: "New booking" }).click();
  await expect(page.getByText(propertyName, { exact: true })).toBeVisible();
  await page.getByLabel("Arrival").fill("2027-04-12");
  await page.getByLabel("Departure").fill("2027-04-14");
  await page.getByRole("button", { name: "Add a Chalet" }).click();
  await page.getByLabel("First name").fill("Martha");
  await page.getByLabel("Last name").fill(guestLast);
  await page.getByRole("button", { name: /^Book/ }).click();
  await expect(page.getByText("Room not assigned yet")).toBeVisible();

  await page.getByRole("button", { name: "Assign room for Chalet" }).click();
  const picker = page.getByLabel("Room for Chalet");
  const room1 = await picker.locator("option", { hasText: /^Room 1 ·/ }).getAttribute("value");
  await picker.selectOption(room1!);
  await page.getByRole("button", { name: "Assign", exact: true }).click();
  await expect(page.getByText("Room 1", { exact: true })).toBeVisible();

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Calendar" }).click();
  await page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName }).click();
  await expect(page.getByText(new RegExp(`^${propertyName} · `))).toBeVisible();
  await page.goto(`${page.url()}&start=2027-04-11`);
  const bar = page.getByRole("link", { name: `Martha ${guestLast}` });
  await expect(bar).toBeVisible();
  // The bar sits in room 1's row: same grid row as the "1" label.
  const row = await bar.evaluate((el) => (el as HTMLElement).style.gridRow);
  const label = page.locator(".sticky", { hasText: /^1CHL/ }).first();
  expect(await label.evaluate((el) => (el as HTMLElement).style.gridRow)).toBe(row);
  await bar.click();
  await expect(page.getByRole("heading", { name: /^LOS-/ })).toBeVisible();
});
