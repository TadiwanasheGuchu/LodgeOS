import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import path from "node:path";

export const PASSWORD = "e2e-password-1234";

/** Creates fresh organisations and staff for this run, using the operator CLI. */
export default function globalSetup() {
  const run = Date.now().toString(36);
  const backend = path.resolve(__dirname, "../../backend");
  const cli = (...args: string[]) =>
    execFileSync("uv", ["run", "python", "-m", "app.cli", ...args], {
      cwd: backend,
      env: { ...process.env, LODGEOS_BOOTSTRAP_PASSWORD: PASSWORD },
      stdio: "pipe",
    });

  const lodge = `e2e-lodge-${run}`;
  const camp = `e2e-camp-${run}`;
  const owner = `owner-${run}@lodge.example.com`;
  const receptionist = `desk-${run}@lodge.example.com`;
  const multi = `multi-${run}@lodge.example.com`;
  const housekeeping = `hk-${run}@lodge.example.com`;
  const maintenance = `fix-${run}@lodge.example.com`;

  cli("bootstrap-organisation", "--name", `Okavango Lodge ${run}`, "--slug", lodge, "--currency", "NAD",
    "--timezone", "Africa/Windhoek", "--country", "NA", "--owner-email", owner, "--owner-name", "Olivia Owner");
  cli("bootstrap-organisation", "--name", `Matobo Camp ${run}`, "--slug", camp, "--currency", "USD",
    "--timezone", "Africa/Harare", "--country", "ZW", "--owner-email", multi, "--owner-name", "Mpho Multi");
  cli("add-member", "--org", lodge, "--email", receptionist, "--name", "Rudo Reception", "--role", "receptionist");
  cli("add-member", "--org", lodge, "--email", multi, "--name", "Mpho Multi", "--role", "manager");
  cli("add-member", "--org", lodge, "--email", housekeeping, "--name", "Hilma Housekeeping", "--role", "housekeeping");
  cli("add-member", "--org", lodge, "--email", maintenance, "--name", "Fanuel Fixit", "--role", "maintenance");

  writeFileSync(
    path.join(__dirname, ".run.json"),
    JSON.stringify({ run, owner, receptionist, multi, housekeeping, maintenance, lodgeName: `Okavango Lodge ${run}`, campName: `Matobo Camp ${run}` }),
  );
}
