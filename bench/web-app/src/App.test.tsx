import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { App } from "./App";

it("adds a todo from the form", () => {
  render(<App />);
  fireEvent.change(screen.getByLabelText("新しいタスク"), { target: { value: "テスト" } });
  fireEvent.click(screen.getByRole("button", { name: "追加" }));
  expect(screen.getByTestId("remaining").textContent).toBe("残り 1 件");
});
