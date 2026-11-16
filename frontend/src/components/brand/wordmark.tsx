import { cn } from "@/lib/utils";

/** Text wordmark. A drawn logo will replace the mark once the brand identity is final. */
export function Wordmark({ className, tone = "forest" }: { className?: string; tone?: "forest" | "white" }) {
  return (
    <span
      className={cn(
        "font-display text-2xl font-semibold tracking-tight",
        tone === "white" ? "text-white" : "text-forest",
        className,
      )}
    >
      Lodge<span className={tone === "white" ? "text-sage" : "text-teal"}>OS</span>
    </span>
  );
}
