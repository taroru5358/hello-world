// 大規模アプリ用のソースを決定的に生成する（CI 上で実行し、生成物はコミットしない）。
// feature ごとに schema（zod）・logic・unit test・MUI コンポーネントを作る。
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const COUNT = Number(process.env.FEATURE_COUNT ?? 300);
const root = join(import.meta.dirname, "..", "src", "generated");
rmSync(root, { recursive: true, force: true });
mkdirSync(root, { recursive: true });

const pad = (n) => String(n).padStart(3, "0");
const exportsList = [];

for (let i = 0; i < COUNT; i++) {
  const id = pad(i);
  const dir = join(root, `f${id}`);
  mkdirSync(dir);
  writeFileSync(
    join(dir, "schema.ts"),
    `import { z } from "zod";

export const Item${id} = z.object({
  id: z.number().int().nonnegative(),
  name: z.string().min(1).max(80),
  price: z.number().nonnegative(),
  tags: z.array(z.string()).max(10),
  createdAt: z.string().datetime(),
});
export type Item${id} = z.infer<typeof Item${id}>;
`,
  );
  writeFileSync(
    join(dir, "logic.ts"),
    `import { format, parseISO } from "date-fns";
import { groupBy, sumBy } from "lodash-es";
import { Item${id} } from "./schema";

export function parseItems${id}(input: unknown[]): Item${id}[] {
  return input.flatMap((x) => {
    const r = Item${id}.safeParse(x);
    return r.success ? [r.data] : [];
  });
}

export function total${id}(items: Item${id}[]): number {
  return Math.round(sumBy(items, (x) => x.price) * 100) / 100;
}

export function byMonth${id}(items: Item${id}[]): Record<string, number> {
  const groups = groupBy(items, (x) => format(parseISO(x.createdAt), "yyyy-MM"));
  return Object.fromEntries(Object.entries(groups).map(([k, v]) => [k, v.length]));
}
`,
  );
  writeFileSync(
    join(dir, "logic.test.ts"),
    `import { describe, expect, it } from "vitest";
import { byMonth${id}, parseItems${id}, total${id} } from "./logic";

const raw = [
  { id: 1, name: "a", price: 10, tags: [], createdAt: "2026-01-05T00:00:00Z" },
  { id: 2, name: "b", price: 5.5, tags: ["x"], createdAt: "2026-01-20T00:00:00Z" },
  { id: 3, name: "", price: 1, tags: [], createdAt: "2026-02-01T00:00:00Z" },
  { id: 4, name: "d", price: 2, tags: [], createdAt: "2026-02-01T00:00:00Z" },
];

describe("feature ${id}", () => {
  it("drops invalid rows", () => {
    expect(parseItems${id}(raw)).toHaveLength(3);
  });
  it("sums prices", () => {
    expect(total${id}(parseItems${id}(raw))).toBeCloseTo(17.5);
  });
  it("groups by month", () => {
    expect(byMonth${id}(parseItems${id}(raw))).toEqual({ "2026-01": 2, "2026-02": 1 });
  });
});
`,
  );
  writeFileSync(
    join(dir, "Card.tsx"),
    `import ShoppingCartIcon from "@mui/icons-material/ShoppingCart";
import { Button, Card, CardActions, CardContent, Chip, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { type Item${id} } from "./schema";
import { total${id} } from "./logic";

export function Card${id}({ items }: { items: Item${id}[] }) {
  const { t } = useTranslation();
  const { data } = useQuery({ queryKey: ["f${id}", items.length], queryFn: () => Promise.resolve(total${id}(items)) });
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h6">{t("feature", { id: "${id}" })}</Typography>
        <Stack direction="row" spacing={1}>
          {items.slice(0, 3).map((x) => (
            <Chip key={x.id} label={x.name} size="small" />
          ))}
        </Stack>
        <Typography variant="body2">{data ?? 0}</Typography>
      </CardContent>
      <CardActions>
        <Button size="small" startIcon={<ShoppingCartIcon />}>
          {t("open")}
        </Button>
      </CardActions>
    </Card>
  );
}
`,
  );
  exportsList.push(`export { Card${id} } from "./f${id}/Card";`);
}
writeFileSync(join(root, "index.ts"), exportsList.join("\n") + "\n");
writeFileSync(join(root, "count.ts"), `export const FEATURE_COUNT = ${COUNT};\n`);
console.log(`generated ${COUNT} features`);
