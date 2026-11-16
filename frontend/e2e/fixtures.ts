import { expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

export const PASSWORD = "e2e-password-1234";

export const seed = JSON.parse(readFileSync(path.join(__dirname, ".run.json"), "utf8")) as {
  run: string;
  owner: string;
  receptionist: string;
  multi: string;
  housekeeping: string;
  maintenance: string;
  lodgeName: string;
  campName: string;
};

export async function signIn(page: Page, email: string, password = PASSWORD) {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Sign in and wait until the app has left the sign-in page. */
export async function signedIn(page: Page, email: string) {
  await signIn(page, email);
  await expect(page).not.toHaveURL(/\/sign-in$/);
}

/** Fails the test if the page reports a Content-Security-Policy violation or a script error. */
export function watchConsole(page: Page) {
  const problems: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") problems.push(msg.text());
  });
  page.on("pageerror", (err) => problems.push(err.message));
  return {
    expectClean: () => expect(problems, problems.join("\n")).toEqual([]),
  };
}
