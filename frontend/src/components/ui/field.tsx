import * as LabelPrimitive from "@radix-ui/react-label";
import { CircleAlert } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/utils";

const controlBase =
  "w-full rounded-md border border-control bg-white px-3 text-[15px] text-charcoal placeholder:text-muted disabled:bg-cloud disabled:text-muted aria-[invalid=true]:border-danger";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input className={cn(controlBase, "h-10", className)} {...props} />;
}

export function Select({ className, ...props }: ComponentProps<"select">) {
  return <select className={cn(controlBase, "h-10 pr-8", className)} {...props} />;
}

export function Label({ className, ...props }: ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      className={cn("text-sm font-medium text-forest", className)}
      {...props}
    />
  );
}

/** Label, control, hint and error, wired together for screen readers. */
export function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: ReactNode;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && !error ? (
        <p id={`${id}-hint`} className="text-[13px] text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} className="flex items-center gap-1.5 text-[13px] text-danger">
          <CircleAlert className="size-3.5 shrink-0" aria-hidden />
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Props that connect a control to its Field's hint and error text. */
export function describedBy(id: string, error?: string, hint?: boolean) {
  const ids = [error ? `${id}-error` : null, hint && !error ? `${id}-hint` : null].filter(Boolean);
  return {
    id,
    "aria-invalid": error ? true : undefined,
    "aria-describedby": ids.length ? ids.join(" ") : undefined,
  } as const;
}
