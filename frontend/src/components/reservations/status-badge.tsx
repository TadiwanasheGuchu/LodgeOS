import { Ban, CircleCheck, CircleDashed, DoorClosed, DoorOpen, UserX } from "lucide-react";
import { StatusChip } from "@/components/rooms/status";
import { RESERVATION_STATUS_LABELS, type ReservationStatus } from "@/lib/types";

const STYLES: Record<ReservationStatus, { className: string; Icon: typeof Ban }> = {
  provisional: { className: "bg-warning-tint text-charcoal ring-warning", Icon: CircleDashed },
  confirmed: { className: "bg-mist text-forest ring-teal/40", Icon: CircleCheck },
  checked_in: { className: "bg-success-tint text-success ring-success/40", Icon: DoorOpen },
  checked_out: { className: "bg-cloud text-muted ring-line", Icon: DoorClosed },
  cancelled: { className: "bg-danger-tint text-danger ring-danger/40", Icon: Ban },
  no_show: { className: "bg-danger-tint text-danger ring-danger/40", Icon: UserX },
};

export function ReservationStatusBadge({ status }: { status: ReservationStatus }) {
  return <StatusChip label={RESERVATION_STATUS_LABELS[status]} {...STYLES[status]} />;
}
