import { expect, test } from "@playwright/test";
import { seed, signedIn } from "./fixtures";

// Runs after the stays spec: Waterberg has chalets 1-6 and room 1 is booked 12-14 April 2027.
const propertyName = `Waterberg Lodge ${seed.run}`;
const problem = `Geyser leaking ${seed.run}`;

async function openMaintenance(page: import("@playwright/test").Page) {
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Maintenance" }).click();
  await expect(page.getByRole("heading", { name: "Maintenance", level: 1 })).toBeVisible();
  const switcher = page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName });
  if (await switcher.count()) {
    await switcher.click();
    await expect(switcher).toHaveAttribute("aria-current", "page");
  }
}

test("housekeeping reports, maintenance blocks the room, calendar shows it, fixing releases it", async ({ page }) => {
  // Housekeeping finds the problem and reports it; they cannot work the ticket.
  await signedIn(page, seed.housekeeping);
  await openMaintenance(page);
  await page.getByRole("button", { name: "Report a problem" }).click();
  const where = page.getByLabel("Where");
  await where.selectOption(await where.locator("option", { hasText: "Room 2" }).getAttribute("value") as string);
  await page.getByLabel("What is wrong?").fill(problem);
  await page.getByLabel("Urgent").check();
  await page.getByRole("button", { name: "Report problem" }).click();
  const ticket = page.getByRole("listitem").filter({ hasText: problem });
  await expect(ticket).toContainText("Room 2 · reported by Hilma Housekeeping");
  await expect(ticket.getByRole("button", { name: "Mark as fixed" })).toHaveCount(0);

  // Maintenance takes it and takes room 2 out of sale.
  await page.context().clearCookies();
  await signedIn(page, seed.maintenance);
  await openMaintenance(page);
  const t = page.getByRole("listitem").filter({ hasText: problem });
  await t.getByRole("button", { name: "Start work" }).click();
  await expect(t).toContainText("with Fanuel Fixit · in progress");
  await t.getByRole("button", { name: "Take room out of sale" }).click();
  await page.getByLabel("First night out").fill("2027-05-03");
  await page.getByLabel("Back on sale").fill("2027-05-05");
  await page.getByRole("button", { name: "Take out of sale", exact: true }).click();
  await expect(t).toContainText("Out of sale");

  // The front desk sees the block on the calendar, in room 2's row.
  await page.context().clearCookies();
  await signedIn(page, seed.receptionist);
  await page.goto("/calendar");
  const cal = page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName });
  const href = (await cal.count()) ? await cal.getAttribute("href") : "/calendar?";
  await page.goto(`${href}&start=2027-05-01`);
  const bar = page.getByTitle(new RegExp(`^Out of sale: ${problem}`));
  await expect(bar).toBeVisible();
  const label = page.locator(".sticky", { hasText: /^2CHL/ }).first();
  expect(await bar.evaluate((el) => (el as HTMLElement).style.gridRow)).toBe(await label.evaluate((el) => (el as HTMLElement).style.gridRow));

  // Fixed: the room goes back on sale.
  await page.context().clearCookies();
  await signedIn(page, seed.maintenance);
  await openMaintenance(page);
  await page.getByRole("listitem").filter({ hasText: problem }).getByRole("button", { name: "Mark as fixed" }).click();
  await page.getByLabel("What was done?").fill("Replaced the pressure valve");
  await page.getByRole("button", { name: "Mark as fixed" }).last().click();
  await expect(page.getByText(problem)).toHaveCount(0);
  await page.getByRole("link", { name: "Closed" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: problem })).toContainText("Done: Replaced the pressure valve");
});

test("housekeeper works today's list on a phone: the checked-out room is cleaned", async ({ page }) => {
  // The stays spec checked a guest out of chalet 6 today.
  await page.setViewportSize({ width: 390, height: 844 });
  await signedIn(page, seed.housekeeping);
  await page.goto("/housekeeping");
  const switcher = page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName });
  if (await switcher.count()) {
    await switcher.click();
    await expect(switcher).toHaveAttribute("aria-current", "page");
  }
  const room = page.getByRole("listitem", { name: "Room 6" });
  await expect(room).toContainText("Departure clean");
  await expect(room).toContainText("Guest left");
  await room.getByRole("button", { name: "Start" }).click();
  await expect(room).toContainText("In progress");
  await room.getByRole("button", { name: "Done" }).click();
  await expect(room).toContainText("Done by Hilma Housekeeping");
  await expect(room.getByRole("button", { name: "Reopen" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await page.goto("/rooms");
  const rooms = page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName });
  if (await rooms.count()) await rooms.click();
  await expect(page.getByRole("group", { name: "Room 6 cleaning status" }).getByRole("button", { name: "Clean" })).toHaveAttribute("aria-pressed", "true");
});
