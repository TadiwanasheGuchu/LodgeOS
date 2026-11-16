"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { describedBy, Field, Input } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import type { Me } from "@/lib/types";

const schema = z.object({
  email: z.string().trim().min(1, "Enter your email address.").email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});
type Values = z.infer<typeof schema>;

export function SignInForm() {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });

  async function onSubmit(values: Values) {
    setFormError(null);
    try {
      const me = await api<Me>("/api/v1/auth/login", { method: "POST", body: values });
      router.replace(me.active_organisation ? "/" : "/select-organisation");
      router.refresh();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="mt-8 flex flex-col gap-5">
      {formError ? <Alert tone="error">{formError}</Alert> : null}
      <Field id="email" label="Email" error={errors.email?.message}>
        <Input
          type="email"
          autoComplete="username"
          inputMode="email"
          {...describedBy("email", errors.email?.message)}
          {...register("email")}
        />
      </Field>
      <Field id="password" label="Password" error={errors.password?.message}>
        <Input
          type="password"
          autoComplete="current-password"
          {...describedBy("password", errors.password?.message)}
          {...register("password")}
        />
      </Field>
      <Button type="submit" size="lg" loading={isSubmitting} className="mt-1 w-full">
        Sign in
      </Button>
    </form>
  );
}
