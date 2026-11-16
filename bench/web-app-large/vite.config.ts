import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  // 生成コード（node 環境で走る logic test）が大半。DOM が要るテストはファイル先頭で jsdom を指定する
  test: { environment: "node", include: ["src/**/*.test.{ts,tsx}"] },
});
