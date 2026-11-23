import { expect, test } from "@playwright/test";
import { deliverEmails, seed, signedIn } from "./fixtures";

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

test("invoice a stay with an extra, issue it, then credit the extra", async ({ page }) => {
  await signedIn(page, seed.receptionist);
  await page.goto("/reservations");
  await page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName }).click();
  await expect(page.getByText(new RegExp(`^${propertyName} · stays from`))).toBeVisible();
  await page.getByRole("link", { name: "New booking" }).click();
  await expect(page.getByText(propertyName, { exact: true })).toBeVisible();
  await page.getByLabel("Arrival").fill("2027-05-20");
  await page.getByLabel("Departure").fill("2027-05-22");
  await page.getByRole("button", { name: "Add a Chalet" }).click();
  await page.getByLabel("First name").fill("Tuyeni");
  await page.getByLabel("Last name").fill(`Amupolo ${seed.run}`);
  await page.getByRole("button", { name: /^Book/ }).click();
  await expect(page.getByRole("heading", { name: /^LOS-/ })).toBeVisible();
  await expect(page.getByText("Not invoiced yet.")).toBeVisible();

  await page.getByRole("button", { name: "Create invoice" }).click();
  const doc = page.getByRole("article", { name: /invoice/i });
  await expect(doc.getByRole("heading", { name: "Draft invoice" })).toBeVisible();
  await expect(doc).toContainText(`Tuyeni Amupolo ${seed.run}`);
  await expect(doc).toContainText("Chalet · Bed and breakfast · 20 May to 22 May 2027 (2 nights)");

  await page.getByRole("button", { name: "Add a line" }).click();
  await page.getByLabel("Description").fill("Dinner, 2 guests");
  await page.getByLabel("Quantity").fill("2");
  await page.getByLabel(/^Price each/).fill("150");
  await page.getByRole("button", { name: "Add line" }).click();
  await expect(doc).toContainText("Dinner, 2 guests");

  await page.getByRole("button", { name: "Issue invoice" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Issue invoice" }).click();
  await expect(doc.getByText(/^INV-\d{6}$/)).toBeVisible();
  const invoiceUrl = page.url();
  // Front desk cannot credit; it is shown how mistakes are corrected.
  await expect(page.getByRole("button", { name: "Credit note" })).toHaveCount(0);
  await expect(page.getByText("Mistakes are corrected with a credit note by a manager or accountant.")).toBeVisible();

  await page.context().clearCookies();
  await signedIn(page, seed.owner);
  await page.goto(invoiceUrl);
  await page.getByRole("button", { name: "Credit note" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: /^Credit all NAD 300\.00/ }).click();
  await dialog.getByLabel("Reason").fill("Dinner was complimentary");
  await dialog.getByRole("button", { name: "Issue credit note" }).click();
  const notes = page.getByRole("region", { name: "Credit notes" });
  await expect(notes).toContainText(/CN-\d{6}/);
  await expect(notes).toContainText("Dinner was complimentary");
  await expect(doc.getByRole("region", { name: "Payments" })).toContainText(/Balance due\s*NAD\s2\s200\.00/);
});

test("deposit on booking, invoice, apply deposit, settle in cash, see the cash-up", async ({ page }) => {
  await signedIn(page, seed.receptionist);
  await page.goto("/reservations");
  await page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName }).click();
  await expect(page.getByText(new RegExp(`^${propertyName} · stays from`))).toBeVisible();
  await page.getByRole("link", { name: "New booking" }).click();
  await expect(page.getByText(propertyName, { exact: true })).toBeVisible();
  await page.getByLabel("Arrival").fill("2027-06-10");
  await page.getByLabel("Departure").fill("2027-06-11");
  await page.getByRole("button", { name: "Add a Chalet" }).click();
  await page.getByLabel("First name").fill("Petrus");
  await page.getByLabel("Last name").fill(`Shikongo ${seed.run}`);
  await page.getByRole("button", { name: /^Book/ }).click();
  await expect(page.getByRole("heading", { name: /^LOS-/ })).toBeVisible();
  const booking = page.url();

  // Deposit by bank transfer before any invoice exists.
  await page.getByRole("button", { name: "Take a deposit" }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("Bank transfer").check();
  await dialog.getByLabel(/^Amount/).fill("500");
  await dialog.getByLabel("Reference (optional)").fill(`EFT-${seed.run}`);
  await dialog.getByRole("button", { name: "Record payment" }).click();
  const panel = page.getByRole("region", { name: "Payments" });
  await expect(panel).toContainText("NAD 500.00 not yet on an invoice");

  await page.getByRole("button", { name: "Create invoice" }).click();
  await page.getByRole("button", { name: "Issue invoice" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Issue invoice" }).click();
  const number = (await page.getByRole("article").getByText(/^INV-\d{6}$/).textContent())!;

  await page.goto(booking);
  await panel.getByRole("button", { name: `Apply to ${number}` }).click();
  await expect(panel).not.toContainText("not yet on an invoice");

  // Settle the rest in cash from the invoice.
  await page.getByRole("link", { name: number }).click();
  const payments = page.getByRole("article").getByRole("region", { name: "Payments" });
  await payments.getByRole("button", { name: "Record payment" }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Cash").check();
  await dialog.getByRole("button", { name: "Record payment" }).click();
  await expect(payments).toContainText(/Balance due\s*NAD 0\.00/);
  await expect(payments.getByRole("button", { name: "Record payment" })).toHaveCount(0);

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Payments" }).click();
  await expect(page.getByRole("heading", { name: "Payments", level: 1 })).toBeVisible();
  const prop = page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName });
  if (await prop.count()) await page.goto((await prop.getAttribute("href"))!);
  const takings = page.getByRole("region", { name: "Cash-up" });
  await expect(takings.getByRole("row", { name: /^Cash/ })).toBeVisible();
  await expect(takings.getByRole("row", { name: /^Bank transfer/ })).toContainText("NAD 500.00");
  await expect(page.getByRole("region", { name: "Payments received" })).toContainText(`EFT-${seed.run}`);
});

test("email a booking confirmation; the worker delivers it in test mode", async ({ page }) => {
  await signedIn(page, seed.receptionist);
  await page.goto("/reservations");
  await page.getByRole("navigation", { name: "Property" }).getByRole("link", { name: propertyName }).click();
  await expect(page.getByText(new RegExp(`^${propertyName} · stays from`))).toBeVisible();
  await page.getByRole("link", { name: "New booking" }).click();
  await expect(page.getByText(propertyName, { exact: true })).toBeVisible();
  await page.getByLabel("Arrival").fill("2027-07-01");
  await page.getByLabel("Departure").fill("2027-07-03");
  await page.getByRole("button", { name: "Add a Chalet" }).click();
  await page.getByLabel("First name").fill("Ndapewa");
  await page.getByLabel("Last name").fill(`Iipinge ${seed.run}`);
  await page.getByRole("button", { name: /^Book/ }).click();
  const reference = (await page.getByRole("heading", { name: /^LOS-/ }).textContent())!.match(/LOS-\w{6}/)![0];

  await page.getByRole("button", { name: "Email confirmation" }).click();
  const dialog = page.getByRole("dialog");
  // No address on file: the API says so, and staff can enter one.
  await dialog.getByRole("button", { name: "Send email" }).click();
  await expect(dialog.getByText("There is no email address on file. Enter one to send to.")).toBeVisible();
  await dialog.getByLabel("Send to").fill(`ndapewa-${seed.run}@example.com`);
  await dialog.getByRole("button", { name: "Send email" }).click();
  const log = page.getByRole("list", { name: "Emails" });
  await expect(log).toContainText(`Your booking ${reference} is confirmed`);
  await expect(log).toContainText("Waiting to send");

  deliverEmails();
  await page.reload();
  await expect(log).toContainText("Sent (test mode: not delivered to the guest)");
});
