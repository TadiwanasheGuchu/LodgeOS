import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { describedBy, Field, Input } from "@/components/ui/field";

describe("Field", () => {
  it("connects label, error and control for assistive technology", () => {
    render(
      <Field id="email" label="Email" error="Enter a valid email address.">
        <Input {...describedBy("email", "Enter a valid email address.")} />
      </Field>,
    );
    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Enter a valid email address.");
  });

  it("uses the hint as description when there is no error", () => {
    render(
      <Field id="tz" label="Timezone" hint="Used for reports.">
        <Input {...describedBy("tz", undefined, true)} />
      </Field>,
    );
    expect(screen.getByLabelText("Timezone")).toHaveAccessibleDescription("Used for reports.");
    expect(screen.getByLabelText("Timezone")).not.toHaveAttribute("aria-invalid");
  });
});
