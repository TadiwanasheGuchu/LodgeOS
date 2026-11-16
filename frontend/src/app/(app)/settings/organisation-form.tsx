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
import type { Organisation } from "@/lib/types";

const schema = z.object({
  name: z.string().trim().min(2, "Enter at least 2 characters.").max(200, "Use 200 characters or fewer."),
  default_currency: z.string().regex(/^[A-Z]{3}$/, "Choose a currency."),
  default_timezone: z.string().min(1, "Choose a timezone."),
  country_code: z.string().regex(/^[A-Z]{2}$/, "Choose a country."),
});
type Values = z.infer<typeof schema>;

export function OrganisationForm({ organisation }: { organisation: Organisation }) {
  const router = useRouter();
  const [result, setResult] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const tzOptions = useMemo(() => timezones(organisation.default_timezone), [organisation.default_timezone]);
  const currencies = CURRENCIES.some((c) => c.code === organisation.default_currency)
    ? CURRENCIES
    : [{ code: organisation.default_currency, name: organisation.default_currency }, ...CURRENCIES];

  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting, isDirty, dirtyFields },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: organisation.name,
      default_currency: organisation.default_currency,
      default_timezone: organisation.default_timezone,
      country_code: organisation.country_code ?? "",
    },
  });

  async function onSubmit(values: Values) {
    setResult(null);
    // Send only changed fields, so the audit log records exactly what changed.
    const changes = Object.fromEntries(
      Object.entries(values).filter(([k]) => dirtyFields[k as keyof Values]),
    );
    try {
      const updated = await api<Organisation>("/api/v1/organisation", { method: "PATCH", body: changes });
      reset({
        name: updated.name,
        default_currency: updated.default_currency,
        default_timezone: updated.default_timezone,
        country_code: updated.country_code ?? "",
      });
      setResult({ tone: "success", message: "Changes saved." });
      router.refresh();
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

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-5">
      {result ? <Alert tone={result.tone}>{result.message}</Alert> : null}

      <Field id="name" label="Organisation name" error={errors.name?.message}>
        <Input autoComplete="organization" {...describedBy("name", errors.name?.message)} {...register("name")} />
      </Field>

      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="default_currency" label="Default currency" error={errors.default_currency?.message}>
          <Select {...describedBy("default_currency", errors.default_currency?.message)} {...register("default_currency")}>
            {currencies.map((c) => (
              <option key={c.code} value={c.code}>
                {c.code} · {c.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field id="country_code" label="Country" error={errors.country_code?.message}>
          <Select {...describedBy("country_code", errors.country_code?.message)} {...register("country_code")}>
            <option value="" disabled>
              Choose a country
            </option>
            {COUNTRIES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <Field
        id="default_timezone"
        label="Default timezone"
        hint="Check-in times, reports and the activity log use this timezone."
        error={errors.default_timezone?.message}
      >
        <Select
          {...describedBy("default_timezone", errors.default_timezone?.message, true)}
          {...register("default_timezone")}
        >
          {tzOptions.map((tz) => (
            <option key={tz} value={tz}>
              {tz.replaceAll("_", " ")}
            </option>
          ))}
        </Select>
      </Field>

      <div className="flex items-center gap-3 border-t border-line pt-5">
        <Button type="submit" loading={isSubmitting} disabled={!isDirty}>
          Save changes
        </Button>
        {isDirty ? (
          <Button type="button" variant="ghost" onClick={() => { reset(); setResult(null); }}>
            Discard
          </Button>
        ) : null}
      </div>
    </form>
  );
}
