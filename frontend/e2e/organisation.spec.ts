import { expect, test } from "@playwright/test";
import { seed, signedIn, signIn } from "./fixtures";

test("owner changes organisation details and sees the change in the activity log", async ({ page }) => {
  await signIn(page, seed.owner);
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Organisation" }).click();
  await expect(page.getByRole("heading", { name: "Organisation" })).toBeVisible();

  const save = page.getByRole("button", { name: "Save changes" });
  await expect(save).toBeDisabled(); // nothing changed yet
  await page.getByLabel("Default currency").selectOption("ZAR");
  await save.click();
  await expect(page.getByRole("status")).toHaveText("Changes saved.");

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Activity log" }).click();
  await expect(page.getByText("Currency: NAD → ZAR")).toBeVisible();
  await expect(page.getByText("Olivia Owner").first()).toBeVisible();

  // Put it back so the test can be repeated.
  await page.goto("/settings");
  await page.getByLabel("Default currency").selectOption("NAD");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status")).toHaveText("Changes saved.");
});

test("owner sees field validation from the form", async ({ page }) => {
  await signedIn(page, seed.owner);
  await page.goto("/settings");
  await page.getByLabel("Organisation name").fill("A");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Enter at least 2 characters.")).toBeVisible();
});

test("receptionist sees only what the role allows", async ({ page }) => {
  await signIn(page, seed.receptionist);
  await expect(page.getByRole("heading", { name: /Hello, Rudo/ })).toBeVisible();

  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Overview" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Team" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Activity log" })).toHaveCount(0);

  await nav.getByRole("link", { name: "Organisation" }).click();
  await expect(page.getByText("Only the organisation owner can change these details.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Save changes" })).toHaveCount(0);

  // Typing the address directly does not help either.
  await page.goto("/team");
  await expect(page).toHaveURL(/\/$/);
});

test("manager sees the team", async ({ page }) => {
  await signIn(page, seed.multi);
  await page.getByRole("button", { name: new RegExp(seed.lodgeName) }).click();
  await expect(page.getByRole("heading", { name: /Hello, Mpho/ })).toBeVisible();
  await page.goto("/team");
  await expect(page.getByRole("cell", { name: "Rudo Reception" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Olivia Owner" })).toBeVisible();
});

test("a user in two organisations chooses one and can switch", async ({ page }) => {
  await signIn(page, seed.multi);
  await expect(page).toHaveURL(/\/select-organisation$/);
  await page.getByRole("button", { name: new RegExp(seed.campName) }).click();
  await expect(page.getByRole("heading", { name: /Hello, Mpho/ })).toBeVisible();
  await expect(page.getByText(`${seed.campName} · Owner`)).toBeVisible();

  await page.getByRole("link", { name: "Switch organisation" }).first().click();
  await page.getByRole("button", { name: new RegExp(seed.lodgeName) }).click();
  await expect(page.getByText(`${seed.lodgeName} · Manager`)).toBeVisible();
});
