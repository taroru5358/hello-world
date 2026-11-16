import { useState } from "react";
import { addTodo, remaining, toggleTodo, type Todo } from "./todo";

export function App() {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [title, setTitle] = useState("");

  return (
    <main>
      <h1>Todo</h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setTodos((prev) => addTodo(prev, title));
          setTitle("");
        }}
      >
        <label>
          新しいタスク
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <button type="submit">追加</button>
      </form>
      <ul>
        {todos.map((t) => (
          <li key={t.id}>
            <label>
              <input type="checkbox" checked={t.done} onChange={() => setTodos((prev) => toggleTodo(prev, t.id))} />
              {t.title}
            </label>
          </li>
        ))}
      </ul>
      <p data-testid="remaining">残り {remaining(todos)} 件</p>
    </main>
  );
}
