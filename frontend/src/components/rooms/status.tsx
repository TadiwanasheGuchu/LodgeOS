import { CircleAlert, CircleCheck, Construction, Sparkles, SprayCan, Wrench } from "lucide-react";
import type { HousekeepingStatus, MaintenanceStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

type ChipStyle = { label: string; className: string; Icon: typeof CircleCheck };

export const HOUSEKEEPING: Record<HousekeepingStatus, ChipStyle> = {
  dirty: { label: "Dirty", className: "bg-warning-tint text-charcoal ring-warning", Icon: SprayCan },
  clean: { label: "Clean", className: "bg-mist text-forest ring-teal/40", Icon: Sparkles },
  inspected: { label: "Inspected", className: "bg-success-tint text-success ring-success/40", Icon: CircleCheck },
};

export const MAINTENANCE: Record<Exclude<MaintenanceStatus, "none">, ChipStyle> = {
  out_of_service: { label: "Out of service", className: "bg-warning-tint text-charcoal ring-warning", Icon: Wrench },
  out_of_order: { label: "Out of order", className: "bg-danger-tint text-danger ring-danger/40", Icon: Construction },
};

export function StatusChip({ label, className, Icon }: ChipStyle & { Icon: typeof CircleAlert }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-[12px] font-medium whitespace-nowrap ring-1 ring-inset",
        className,
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {label}
    </span>
  );
}

export function HousekeepingChip({ status }: { status: HousekeepingStatus }) {
  return <StatusChip {...HOUSEKEEPING[status]} />;
}

export function MaintenanceChip({ status }: { status: MaintenanceStatus }) {
  if (status === "none") return null;
  return <StatusChip {...MAINTENANCE[status]} />;
}
