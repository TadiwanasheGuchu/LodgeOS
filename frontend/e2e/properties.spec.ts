import { expect, test } from "@playwright/test";
import { seed, signedIn } from "./fixtures";

test.describe.configure({ mode: "serial" });

const propertyName = `Waterberg Lodge ${seed.run}`;

test("owner sets up a property, a room type and a range of rooms", async ({ page }) => {
  await signedIn(page, seed.owner);
  await page.goto("/properties");
  await page.getByRole("link", { name: "Add property" }).click();

  await page.getByLabel("Property name").fill(propertyName);
  await page.getByLabel("Type", { exact: true }).selectOption("lodge");
  await page.getByLabel("Check-in from").fill("13:00");
  await page.getByLabel("Town or city").fill("Otjiwarongo");
  await page.getByRole("button", { name: "Create property" }).click();

  // Lands on room types, which is the next setup step.
  await expect(page.getByRole("heading", { name: propertyName })).toBeVisible();
  await expect(page.getByRole("link", { name: "Room types" })).toHaveAttribute("aria-current", "page");

  await page.getByRole("button", { name: "Add room type" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name").fill("Chalet");
  await dialog.getByLabel("Code").fill("chl");
  await dialog.getByLabel("Maximum guests").fill("1"); // below the 2 included: invalid
  await dialog.getByRole("button", { name: "Add room type" }).click();
  await expect(dialog.getByText("Must be at least the guests included in the rate.")).toBeVisible();
  await dialog.getByLabel("Maximum guests").fill("4");
  await dialog.getByLabel("Maximum adults").fill("3");
  await dialog.getByRole("button", { name: "Add room type" }).click();
  await expect(page.getByText("CHL")).toBeVisible();
  await expect(page.getByText("2 included, up to 4 guests")).toBeVisible();

  await page.getByRole("link", { name: "Rooms", exact: true }).click();
  await page.getByRole("button", { name: "Add rooms" }).click();
  await page.getByLabel("Room numbers").fill("1-6");
  await expect(page.getByText("6 rooms: 1, 2, 3, 4, 5, 6")).toBeVisible();
  await page.getByRole("button", { name: "Add 6 rooms" }).click();
  await expect(page.getByText("6 active rooms.")).toBeVisible();

  // Adding an existing number is refused and nothing is created.
  await page.getByRole("button", { name: "Add rooms" }).click();
  await page.getByLabel("Room numbers").fill("6-7");
  await page.getByRole("button", { name: "Add 2 rooms" }).click();
  await expect(page.getByRole("dialog").getByText("These room numbers already exist: 6.")).toBeVisible();
});

test("housekeeping marks a room clean from a phone-sized screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signedIn(page, seed.housekeeping);
  await page.goto("/rooms");
  // One property: no switcher, the property name is shown under the heading.
  await expect(page.getByText(propertyName)).toBeVisible();

  const room = page.getByRole("group", { name: "Room 3 cleaning status" });
  await expect(room.getByRole("button", { name: "Dirty" })).toHaveAttribute("aria-pressed", "true");
  await room.getByRole("button", { name: "Clean" }).click();
  await expect(room.getByRole("button", { name: "Clean" })).toHaveAttribute("aria-pressed", "true");

  // Housekeeping cannot take rooms out of order.
  await expect(page.getByRole("button", { name: /Maintenance for room/ })).toHaveCount(0);

  // The change survives a reload, so it was saved.
  await page.reload();
  await page.getByRole("button", { name: "Clean" }).first().waitFor();
  const filter = page.getByRole("group", { name: "Filter rooms" });
  await expect(filter.getByRole("button", { name: /Clean/ })).toContainText("1");

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("maintenance takes a room out of order with a reason, then fixes it", async ({ page }) => {
  await signedIn(page, seed.maintenance);
  await page.goto("/rooms");
  await expect(page.getByText(propertyName)).toBeVisible();

  await page.getByRole("button", { name: "Maintenance for room 5" }).click();
  const dialog = page.getByRole("dialog", { name: "Room 5 maintenance" });
  await dialog.getByLabel("Out of order").check();
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog.getByText("Describe the problem")).toBeVisible();
  await dialog.getByLabel("What is wrong?").fill("Geyser leaking into ceiling");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Geyser leaking into ceiling")).toBeVisible();
  await expect(page.getByText("Out of order")).toBeVisible();

  // Cleaning status is a separate thing and is unchanged.
  await expect(page.getByRole("group", { name: "Room 5 cleaning status" })).toHaveCount(0); // no housekeeping rights

  await page.getByRole("button", { name: "Maintenance for room 5" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Mark as fixed" }).click();
  await expect(page.getByText("Geyser leaking into ceiling")).toHaveCount(0);
});

test("staff without setup rights can view properties but not change them", async ({ page }) => {
  await signedIn(page, seed.housekeeping);
  await page.goto("/properties");
  await expect(page.getByRole("link", { name: "Add property" })).toHaveCount(0);
  await page.goto("/properties/new");
  await expect(page).toHaveURL(/\/properties$/);
});
