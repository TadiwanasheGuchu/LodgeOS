import { expect, test, type Page } from "@playwright/test";
import { seed, signedIn } from "./fixtures";

test.describe.configure({ mode: "serial" });

/** Calls the API from the signed-in page, with the CSRF header, like the app does. */
async function apiPost(page: Page, path: string, body: unknown) {
  const cookies = await page.context().cookies();
  let token = cookies.find((c) => c.name === "lodgeos_csrf")?.value;
  if (!token) {
    await page.request.get("/api/v1/auth/csrf");
    token = (await page.context().cookies()).find((c) => c.name === "lodgeos_csrf")?.value;
  }
  const res = await page.request.post(path, { data: body, headers: { "X-CSRF-Token": token! } });
  expect(res.ok(), await res.text()).toBe(true);
  return res.json();
}

const propertyName = `Spitzkoppe Camp ${seed.run}`;
const otherProperty = `Cape Cross Lodge ${seed.run}`;
const inviteeEmail = `panduleni-${seed.run}@lodge.example.com`;
let inviteUrl = "";

test("owner invites a receptionist for one property and gets a link", async ({ page }) => {
  await signedIn(page, seed.owner);
  await apiPost(page, "/api/v1/properties", { name: propertyName, property_type: "lodge" });
  await apiPost(page, "/api/v1/properties", { name: otherProperty, property_type: "lodge" });

  await page.goto("/team");
  await page.getByRole("button", { name: "Invite someone" }).click();
  const dialog = page.getByRole("dialog", { name: "Invite someone" });
  await dialog.getByLabel("Name").fill("Panduleni Amukoto");
  await dialog.getByLabel("Email").fill(inviteeEmail);
  await dialog.getByLabel("Role").selectOption({ label: "Receptionist" });
  await dialog.getByLabel("Where").selectOption({ label: propertyName });
  await dialog.getByRole("button", { name: "Create invitation link" }).click();

  const linkDialog = page.getByRole("dialog", { name: "Send this link to Panduleni Amukoto" });
  inviteUrl = await linkDialog.getByLabel("Invitation link").inputValue();
  expect(inviteUrl).toMatch(/\/invite\/[A-Za-z0-9_-]{40,}$/);
  await expect(linkDialog.getByRole("link", { name: "Send on WhatsApp" })).toHaveAttribute("href", /^https:\/\/wa\.me\/\?text=/);
  await page.keyboard.press("Escape");

  await expect(page.getByText("Invitations not yet accepted")).toBeVisible();
  await expect(page.getByText(`${inviteeEmail} · Receptionist at ${propertyName}`)).toBeVisible();
});

test("the invited person sets a password, joins and sees only their property", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(inviteUrl);
  await expect(page.getByRole("heading", { name: /^Join Okavango Lodge/ })).toBeVisible();
  await expect(page.getByText(`Receptionist at ${propertyName}`)).toBeVisible();

  await page.getByLabel("Choose a password").fill("short");
  await page.getByRole("button", { name: /^Join/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: "at least 12 characters" })).toBeVisible();

  await page.getByLabel("Choose a password").fill("a long and memorable password");
  await page.getByLabel("Type it again").fill("a long and memorable password");
  await page.getByRole("button", { name: /^Join/ }).click();
  await expect(page.getByRole("heading", { name: "Hello, Panduleni" })).toBeVisible();
  await expect(page.getByText(/Receptionist \(1 property\)/).first()).toBeVisible();

  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Room status" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Team" })).toHaveCount(0);

  await nav.getByRole("link", { name: "Properties" }).click();
  await expect(page.getByRole("link", { name: new RegExp(propertyName) })).toBeVisible();
  await expect(page.getByText(otherProperty)).toHaveCount(0);

  // The link cannot be used again.
  const again = await context.newPage();
  await again.goto(inviteUrl);
  await expect(again.getByText("This invitation has already been used. Sign in instead.")).toBeVisible();
  await context.close();
});

test("owner sees the new member and can remove their role", async ({ page }) => {
  await signedIn(page, seed.owner);
  await page.goto("/team");
  await expect(page.getByText("Invitations not yet accepted")).toHaveCount(0);
  const chip = `Receptionist · ${propertyName}`;
  await expect(page.getByText(chip)).toBeVisible();
  await page.getByRole("button", { name: `Remove ${chip} from Panduleni Amukoto` }).click();
  await expect(page.getByText(chip)).toHaveCount(0);
});

test("a manager cannot offer the owner role", async ({ page }) => {
  await signedIn(page, seed.multi);
  await page.getByRole("button", { name: new RegExp(seed.lodgeName) }).click();
  await expect(page.getByRole("heading", { name: /Hello, Mpho/ })).toBeVisible();
  await page.goto("/team");
  await page.getByRole("button", { name: "Invite someone" }).click();
  const options = await page.getByRole("dialog").getByLabel("Role").locator("option").allTextContents();
  expect(options).not.toContain("Owner");
  expect(options).toContain("Receptionist");
  // Nor remove an owner's role.
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: /^Remove Owner/ })).toHaveCount(0);
});
