"use client";

import { useEffect, useState } from "react";

function format(timeZone: string) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());
}

/** Current time at the property, which may differ from the device's timezone. */
export function PropertyClock({ timeZone }: { timeZone: string }) {
  const [now, setNow] = useState<string | null>(null);
  useEffect(() => {
    const tick = () => setNow(format(timeZone));
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, [timeZone]);
  // Rendered on the client only, so server and browser never disagree about the minute.
  return <time suppressHydrationWarning>{now ?? " "}</time>;
}
