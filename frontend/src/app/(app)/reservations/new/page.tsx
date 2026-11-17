import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { accessOf } from "@/lib/access";
import { todayIn } from "@/lib/dates";
import { apiGet, requireOrganisation, ServerApiError } from "@/lib/server/api";
import type { PropertySummary, RatePlan } from "@/lib/types";
import { BookingForm } from "./booking-form";

export const metadata: Metadata = { title: "New booking" };

export default async function NewReservationPage({ searchParams }: PageProps<"/reservations/new">) {
  const me = await requireOrganisation();
  const access = accessOf(me);
  const properties = (await apiGet<PropertySummary[]>("/api/v1/properties")).filter((p) =>
    access.canAt("reservations.manage", p.id),
  );
  if (properties.length === 0) redirect("/reservations");
  const { property: requested } = await searchParams;
  const current = properties.find((p) => p.id === requested) ?? properties[0];

  let plans: RatePlan[] = [];
  try {
    plans = (await apiGet<RatePlan[]>(`/api/v1/properties/${current.id}/rate-plans`)).filter((p) => p.status === "active");
  } catch (err) {
    if (!(err instanceof ServerApiError && err.status === 403)) throw err;
  }

  return (
    <>
      <PageHeader title="New booking" description={current.name} />
      {plans.length === 0 ? (
        <Alert tone="info">This property has no active rate plans, or your role cannot see them. Set up rates before taking bookings.</Alert>
      ) : (
        <BookingForm property={current} plans={plans} today={todayIn(current.timezone)} />
      )}
    </>
  );
}
