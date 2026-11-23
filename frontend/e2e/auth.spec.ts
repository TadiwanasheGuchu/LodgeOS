import { expect, test } from "@playwright/test";
import { seed, signIn, watchConsole } from "./fixtures";

test("signed-out visitors are sent to sign in", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/sign-in$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("sign-in validates input before calling the API", async ({ page }) => {
  await page.goto("/sign-in");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Enter your email address.")).toBeVisible();
  await expect(page.getByText("Enter your password.")).toBeVisible();
  await expect(page.getByLabel("Email")).toHaveAttribute("aria-invalid", "true");
});

test("wrong password shows a single, non-revealing message", async ({ page }) => {
  await signIn(page, seed.owner, "not-the-password");
  await expect(page.locator("form").getByRole("alert")).toHaveText("Email or password is incorrect.");
  await expect(page).toHaveURL(/\/sign-in$/);
});

test("pages are served with a nonce-based CSP and run without violations", async ({ page }) => {
  const console = watchConsole(page);
  const response = await page.goto("/sign-in");
  const csp = response?.headers()["content-security-policy"] ?? "";
  expect(csp).toContain("script-src 'self' 'nonce-");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).not.toContain("unsafe-eval");
  await signIn(page, seed.owner);
  await expect(page.getByRole("heading", { name: /Hello, Olivia/ })).toBeVisible();
  console.expectClean();
});

test("sign out ends the session", async ({ page }) => {
  await signIn(page, seed.owner);
  await expect(page.getByRole("heading", { name: /Hello, Olivia/ })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).first().click();
  await expect(page).toHaveURL(/\/sign-in$/);
  await page.goto("/settings");
  await expect(page).toHaveURL(/\/sign-in$/);
});

test("the app is installable: manifest and icons are served", async ({ request }) => {
  const res = await request.get("/manifest.webmanifest");
  expect(res.ok()).toBe(true);
  const manifest = await res.json();
  expect(manifest).toMatchObject({ name: "LodgeOS", display: "standalone", theme_color: "#123C35" });
  for (const icon of manifest.icons as { src: string }[]) {
    const img = await request.get(icon.src);
    expect(img.ok(), icon.src).toBe(true);
    expect(img.headers()["content-type"]).toBe("image/png");
  }
});

test("credentials never reach the URL, even if the form is sent before scripts load", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill("someone@example.com");
  await page.getByLabel("Password").fill("not-in-the-url-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForLoadState();
  expect(page.url()).not.toContain("not-in-the-url");
  expect(page.url()).not.toContain("someone");
  await context.close();
});
