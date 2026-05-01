import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { SearchBar } from "@/components/SearchBar";
import { searchTrailsByName } from "@/lib/graphql";

const trailA = {
  id: 1,
  name: "Alpha Trail",
  region: "WA",
  location: null,
  difficulty: "easy",
  length_km: 2.0,
  elevation_gain_m: 100,
  traversability_score: 0.9
};

const trailB = {
  id: 2,
  name: "Beta Trail",
  region: "WA",
  location: null,
  difficulty: "moderate",
  length_km: 5.0,
  elevation_gain_m: 200,
  traversability_score: 0.8
};

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock
  })
}));

vi.mock("@/lib/graphql", () => ({
  searchTrailsByName: vi.fn()
}));

describe("SearchBar", () => {
  it("navigates to trail page on single search result", async () => {
    vi.mocked(searchTrailsByName).mockResolvedValue([
      {
        id: 42,
        name: "Demo Trail",
        region: "WA",
        location: null,
        difficulty: "easy",
        length_km: 2.0,
        elevation_gain_m: 100,
        traversability_score: 0.9
      }
    ]);

    render(<SearchBar />);
    fireEvent.change(screen.getByLabelText("Search a trail by name"), {
      target: { value: "demo" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/trails/42");
    });
  });

  it("reopens the list with ArrowDown after Escape, and selects with Enter", async () => {
    vi.mocked(searchTrailsByName).mockResolvedValue([trailA, trailB]);
    const user = userEvent.setup();
    render(<SearchBar />);

    const input = screen.getByLabelText("Search a trail by name");
    await user.type(input, "alp");
    await waitFor(() => expect(screen.getByRole("listbox")).toBeInTheDocument());

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument());

    input.focus();
    await user.keyboard("{ArrowDown}");
    await waitFor(() => {
      expect(screen.getByRole("listbox")).toBeInTheDocument();
      expect(input).toHaveAttribute("aria-expanded", "true");
    });

    await user.keyboard("{Enter}");
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/trails/1");
    });
  });
});
