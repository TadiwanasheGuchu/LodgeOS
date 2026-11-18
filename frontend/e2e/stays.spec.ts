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

test("arrival today: check in, check out, room goes to housekeeping", async ({ page }) => {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Windhoek" }).format(new Date());
  const tomorrow = new Date(Date.parse(`${today}T00:00:00Z`) + 86_400_000).toISOString().slice(0, 10);
  await signedIn(page, seed.receptionist);
  await page.goto("/reservations");
  await page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName }).click();
  await expect(page.getByText(new RegExp(`^${propertyName} · stays from`))).toBeVisible();
  await page.getByRole("link", { name: "New booking" }).click();
  await expect(page.getByText(propertyName, { exact: true })).toBeVisible();
  await page.getByLabel("Arrival").fill(today);
  await page.getByLabel("Departure").fill(tomorrow);
  await page.getByRole("button", { name: "Add a Chalet" }).click();
  await page.getByLabel("First name").fill("Selma");
  await page.getByLabel("Last name").fill(`Kandjii ${seed.run}`);
  await page.getByRole("button", { name: /^Book/ }).click();
  await expect(page.getByRole("heading", { name: /^LOS-/ })).toBeVisible();

  // Check-in needs a room.
  await page.getByRole("button", { name: "Check in" }).click();
  await expect(page.getByText("Assign a room to every booked room before check-in.")).toBeVisible();
  await page.getByRole("button", { name: "Assign room for Chalet" }).click();
  const picker = page.getByLabel("Room for Chalet");
  const room6 = await picker.locator("option", { hasText: /^Room 6 ·/ }).getAttribute("value");
  await picker.selectOption(room6!);
  await page.getByRole("button", { name: "Assign", exact: true }).click();
  await expect(page.getByText("Room 6", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Check in" }).click();
  await expect(page.getByText("Checked in", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel booking" })).toHaveCount(0);
  await page.getByRole("button", { name: "Check out" }).click();
  await expect(page.getByText("Checked out", { exact: true }).first()).toBeVisible();

  await page.goto("/rooms");
  const switcher = page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName });
  if (await switcher.count()) await switcher.click();
  await expect(page.getByRole("group", { name: "Room 6 cleaning status" }).getByRole("button", { name: "Dirty" })).toHaveAttribute("aria-pressed", "true");
});
