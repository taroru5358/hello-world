import { describe, expect, it } from "vitest";
import { addTodo, remaining, toggleTodo } from "./todo";

describe("todo", () => {
  it("adds trimmed titles and ignores blanks", () => {
    const one = addTodo([], "  牛乳を買う ");
    expect(one).toEqual([{ id: 1, title: "牛乳を買う", done: false }]);
    expect(addTodo(one, "   ")).toBe(one);
  });

  it("toggles and counts remaining", () => {
    const todos = toggleTodo(addTodo(addTodo([], "a"), "b"), 1);
    expect(remaining(todos)).toBe(1);
  });
});
