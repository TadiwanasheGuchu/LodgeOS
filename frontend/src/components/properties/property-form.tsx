"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { describedBy, Field, Input, Select } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { COUNTRIES, CURRENCIES, timezones } from "@/lib/reference-data";
import { PROPERTY_TYPE_LABELS, type Property, type PropertyType } from "@/lib/types";

const optional = (max: number) => z.string().trim().max(max, `Use ${max} characters or fewer.`);

const schema = z.object({
  name: z.string().trim().min(2, "Enter at least 2 characters.").max(200),
  property_type: z.enum(Object.keys(PROPERTY_TYPE_LABELS) as [PropertyType, ...PropertyType[]]),
  timezone: z.string().min(1, "Choose a timezone."),
  currency: z.string().regex(/^[A-Z]{3}$/, "Choose a currency."),
  country_code: z.string().regex(/^[A-Z]{2}$/, "Choose a country."),
  check_in_time: z.string().regex(/^\d{2}:\d{2}$/, "Enter a time."),
  check_out_time: z.string().regex(/^\d{2}:\d{2}$/, "Enter a time."),
  address_line1: optional(200),
  address_line2: optional(200),
  city: optional(100),
  region: optional(100),
  postal_code: optional(20),
  phone: optional(40),
  email: z.union([z.literal(""), z.string().trim().email("Enter a valid email address.")]),
  legal_name: optional(200),
  tax_number: optional(50),
  weekend_nights: z.array(z.string()),
});
type Values = z.infer<typeof schema>;

const WEEKDAYS: [number, string][] = [
  [1, "Mon"],
  [2, "Tue"],
  [3, "Wed"],
  [4, "Thu"],
  [5, "Fri"],
  [6, "Sat"],
  [7, "Sun"],
];

const TEXT_FIELDS = ["address_line1", "address_line2", "city", "region", "postal_code", "phone", "email", "legal_name", "tax_number"] as const;

function toValues(p: Partial<Property>, defaults: { timezone: string; currency: string; country: string | null }): Values {
  return {
    name: p.name ?? "",
    property_type: p.property_type ?? "guesthouse",
    timezone: p.timezone ?? defaults.timezone,
    currency: p.currency ?? defaults.currency,
    country_code: p.country_code ?? defaults.country ?? "",
    check_in_time: (p.check_in_time ?? "14:00").slice(0, 5),
    check_out_time: (p.check_out_time ?? "10:00").slice(0, 5),
    address_line1: p.address_line1 ?? "",
    address_line2: p.address_line2 ?? "",
    city: p.city ?? "",
    region: p.region ?? "",
    postal_code: p.postal_code ?? "",
    phone: p.phone ?? "",
    email: p.email ?? "",
    legal_name: p.legal_name ?? "",
    tax_number: p.tax_number ?? "",
    weekend_nights: (p.weekend_nights ?? [5, 6]).map(String),
  };
}

export function PropertyForm({
  property,
  defaults,
}: {
  property?: Property;
  defaults: { timezone: string; currency: string; country: string | null };
}) {
  const router = useRouter();
  const [result, setResult] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const initial = useMemo(() => toValues(property ?? {}, defaults), [property, defaults]);
  const tzOptions = useMemo(() => timezones(initial.timezone), [initial.timezone]);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting, isDirty, dirtyFields },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: initial });

  async function onSubmit(values: Values) {
    setResult(null);
    const body: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(values)) {
      if (property && !dirtyFields[k as keyof Values]) continue;
      if (k === "weekend_nights") {
        if (property) body[k] = (v as string[]).map(Number);
        continue; // new properties use the default, Friday and Saturday nights
      }
      body[k] = (TEXT_FIELDS as readonly string[]).includes(k) && v === "" ? null : v;
    }
    try {
      if (property) {
        const saved = await api<Property>(`/api/v1/properties/${property.id}`, { method: "PATCH", body });
        reset(toValues(saved, defaults));
        setResult({ tone: "success", message: "Changes saved." });
        router.refresh();
      } else {
        const created = await api<Property>("/api/v1/properties", { method: "POST", body });
        router.push(`/properties/${created.id}/room-types`);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        for (const [field, message] of Object.entries(err.fieldErrors)) {
          if (field in values) setError(field as keyof Values, { message });
        }
        setResult({ tone: "error", message: err.message });
      } else {
        setResult({ tone: "error", message: "Could not save. Please try again." });
      }
    }
  }

  const err = (k: keyof Values) => errors[k]?.message;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-6">
      {result ? <Alert tone={result.tone}>{result.message}</Alert> : null}

      <fieldset className="grid gap-5 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold text-forest">Property</legend>
        <div className="sm:col-span-2">
          <Field id="name" label="Property name" error={err("name")}>
            <Input {...describedBy("name", err("name"))} {...register("name")} />
          </Field>
        </div>
        <Field id="property_type" label="Type" error={err("property_type")}>
          <Select {...describedBy("property_type", err("property_type"))} {...register("property_type")}>
            {Object.entries(PROPERTY_TYPE_LABELS).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </Select>
        </Field>
        <Field id="country_code" label="Country" error={err("country_code")}>
          <Select {...describedBy("country_code", err("country_code"))} {...register("country_code")}>
            <option value="" disabled>Choose a country</option>
            {COUNTRIES.map((c) => (
              <option key={c.code} value={c.code}>{c.name}</option>
            ))}
          </Select>
        </Field>
      </fieldset>

      <fieldset className="grid gap-5 border-t border-line pt-5 sm:grid-cols-2">
        <legend className="sr-only">Time and money</legend>
        <p className="text-sm font-semibold text-forest sm:col-span-2">Time and money</p>
        <Field id="timezone" label="Timezone" hint="Arrival dates, check-in times and reports use this timezone." error={err("timezone")}>
          <Select {...describedBy("timezone", err("timezone"), true)} {...register("timezone")}>
            {tzOptions.map((tz) => (
              <option key={tz} value={tz}>{tz.replaceAll("_", " ")}</option>
            ))}
          </Select>
        </Field>
        <Field id="currency" label="Currency" hint="Rates and invoices for this property." error={err("currency")}>
          <Select {...describedBy("currency", err("currency"), true)} {...register("currency")}>
            {CURRENCIES.map((c) => (
              <option key={c.code} value={c.code}>{c.code} · {c.name}</option>
            ))}
          </Select>
        </Field>
        <Field id="check_in_time" label="Check-in from" error={err("check_in_time")}>
          <Input type="time" {...describedBy("check_in_time", err("check_in_time"))} {...register("check_in_time")} />
        </Field>
        <Field id="check_out_time" label="Check-out by" error={err("check_out_time")}>
          <Input type="time" {...describedBy("check_out_time", err("check_out_time"))} {...register("check_out_time")} />
        </Field>
      </fieldset>

      {property ? (
        <fieldset className="border-t border-line pt-5">
          <legend className="text-sm font-semibold text-forest">Weekend nights</legend>
          <p className="mt-1 mb-3 text-[13px] text-muted">Nights that use weekend prices. A night is named by its date: Friday night is the night from Friday to Saturday.</p>
          <div className="flex flex-wrap gap-2">
            {WEEKDAYS.map(([value, label]) => (
              <label key={value} className="flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm has-[:checked]:border-forest has-[:checked]:bg-mist">
                <input type="checkbox" value={String(value)} className="size-4 accent-forest" {...register("weekend_nights")} />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
      ) : null}

      <fieldset className="grid gap-5 border-t border-line pt-5 sm:grid-cols-2">
        <legend className="sr-only">Address and contact</legend>
        <p className="text-sm font-semibold text-forest sm:col-span-2">Address and contact</p>
        <div className="sm:col-span-2">
          <Field id="address_line1" label="Street address" error={err("address_line1")}>
            <Input autoComplete="address-line1" {...describedBy("address_line1", err("address_line1"))} {...register("address_line1")} />
          </Field>
        </div>
        <div className="sm:col-span-2">
          <Field id="address_line2" label="Address line 2 (optional)" error={err("address_line2")}>
            <Input autoComplete="address-line2" {...describedBy("address_line2", err("address_line2"))} {...register("address_line2")} />
          </Field>
        </div>
        <Field id="city" label="Town or city" error={err("city")}>
          <Input autoComplete="address-level2" {...describedBy("city", err("city"))} {...register("city")} />
        </Field>
        <Field id="region" label="Region" error={err("region")}>
          <Input autoComplete="address-level1" {...describedBy("region", err("region"))} {...register("region")} />
        </Field>
        <Field id="postal_code" label="Postal code" error={err("postal_code")}>
          <Input autoComplete="postal-code" {...describedBy("postal_code", err("postal_code"))} {...register("postal_code")} />
        </Field>
        <Field id="phone" label="Phone" error={err("phone")}>
          <Input type="tel" autoComplete="tel" {...describedBy("phone", err("phone"))} {...register("phone")} />
        </Field>
        <div className="sm:col-span-2">
          <Field id="email" label="Reservations email" error={err("email")}>
            <Input type="email" {...describedBy("email", err("email"))} {...register("email")} />
          </Field>
        </div>
      </fieldset>

      <fieldset className="grid gap-5 border-t border-line pt-5 sm:grid-cols-2">
        <legend className="sr-only">Invoicing</legend>
        <p className="text-sm font-semibold text-forest sm:col-span-2">Invoicing</p>
        <Field id="legal_name" label="Registered business name" hint="Printed on invoices. Leave empty to use the property name." error={err("legal_name")}>
          <Input autoComplete="organization" {...describedBy("legal_name", err("legal_name"))} {...register("legal_name")} />
        </Field>
        <Field id="tax_number" label="Tax registration number" hint="With a number, invoices are titled “Tax invoice”." error={err("tax_number")}>
          <Input className="font-mono" {...describedBy("tax_number", err("tax_number"))} {...register("tax_number")} />
        </Field>
      </fieldset>

      <div className="flex items-center gap-3 border-t border-line pt-5">
        <Button type="submit" loading={isSubmitting} disabled={Boolean(property) && !isDirty}>
          {property ? "Save changes" : "Create property"}
        </Button>
        {property && isDirty ? (
          <Button type="button" variant="ghost" onClick={() => { reset(); setResult(null); }}>
            Discard
          </Button>
        ) : null}
      </div>
    </form>
  );
}
