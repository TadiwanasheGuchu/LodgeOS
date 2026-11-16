import { CircleAlert, CircleCheck, Info } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const styles = {
  error: { box: "border-danger/30 bg-danger-tint text-danger", Icon: CircleAlert },
  success: { box: "border-success/30 bg-success-tint text-success", Icon: CircleCheck },
  info: { box: "border-teal/30 bg-mist text-forest", Icon: Info },
} as const;

export function Alert({
  tone = "info",
  children,
  className,
}: {
  tone?: keyof typeof styles;
  children: ReactNode;
  className?: string;
}) {
  const { box, Icon } = styles[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn("flex items-start gap-2.5 rounded-md border px-3.5 py-3 text-sm", box, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}
