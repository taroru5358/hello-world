import { expect, test } from "@playwright/test";

test("add and complete a todo", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("新しいタスク").fill("E2E のタスク");
  await page.getByRole("button", { name: "追加" }).click();
  await expect(page.getByTestId("remaining")).toHaveText("残り 1 件");
  await page.getByLabel("E2E のタスク").check();
  await expect(page.getByTestId("remaining")).toHaveText("残り 0 件");
});
