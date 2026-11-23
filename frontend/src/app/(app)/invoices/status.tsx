import { CircleCheck, FilePen, FileX, Undo2 } from "lucide-react";
import { StatusChip } from "@/components/rooms/status";

export function InvoiceStatusChip({ status, fullyCredited = false }: { status: "draft" | "issued" | "discarded"; fullyCredited?: boolean }) {
  if (fullyCredited) return <StatusChip label="Credited" className="bg-cloud text-muted ring-line" Icon={Undo2} />;
  if (status === "draft") return <StatusChip label="Draft" className="bg-warning-tint text-charcoal ring-warning" Icon={FilePen} />;
  if (status === "discarded") return <StatusChip label="Discarded" className="bg-cloud text-muted ring-line" Icon={FileX} />;
  return <StatusChip label="Issued" className="bg-success-tint text-success ring-success/40" Icon={CircleCheck} />;
}
