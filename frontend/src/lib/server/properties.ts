import "server-only";
import { notFound } from "next/navigation";
import { apiGet, ServerApiError } from "@/lib/server/api";
import type { Property } from "@/lib/types";

/** A property of the current organisation, or the 404 page. */
export async function loadProperty(id: string): Promise<Property> {
  try {
    return await apiGet<Property>(`/api/v1/properties/${id}`);
  } catch (err) {
    if (err instanceof ServerApiError && (err.status === 404 || err.status === 422)) notFound();
    throw err;
  }
}
