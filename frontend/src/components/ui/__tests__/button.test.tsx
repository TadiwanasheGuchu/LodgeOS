import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("renders as its child element with asChild", () => {
    render(
      <Button asChild>
        <a href="#add-property">Add property</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Add property" });
    expect(link).toHaveAttribute("href", "#add-property");
    expect(link.className).toContain("bg-forest");
  });

  it("is disabled and busy while loading", () => {
    render(<Button loading>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });
});
