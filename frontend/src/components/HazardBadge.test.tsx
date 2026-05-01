import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import { HazardBadge } from "@/components/HazardBadge";

describe("HazardBadge", () => {
  it("renders specific guidance for known hazard type", () => {
    render(<HazardBadge type="snow" severity="medium" />);

    expect(screen.getByText("snow")).toBeInTheDocument();
    expect(screen.getByText("Use traction and start early before slush develops.")).toBeInTheDocument();
    expect(screen.getByText("medium")).toBeInTheDocument();
  });

  it("renders fallback guidance for unknown hazard type", () => {
    render(<HazardBadge type="icefall" severity="high" />);

    expect(screen.getByText("Proceed carefully and review the latest trail reports.")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
  });
});
