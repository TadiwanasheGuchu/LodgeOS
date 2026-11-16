import { AppShell } from "@/components/shell/app-shell";
import { requireOrganisation } from "@/lib/server/api";

export default async function AppLayout({ children }: LayoutProps<"/">) {
  const me = await requireOrganisation();
  return <AppShell me={me}>{children}</AppShell>;
}
