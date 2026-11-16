import { Container, Grid, Typography } from "@mui/material";
import * as Features from "./generated";
import { FEATURE_COUNT } from "./generated/count";

const cards = Object.values(Features) as Array<(p: { items: [] }) => React.JSX.Element>;

export function Catalog() {
  return (
    <Container>
      <Typography variant="h4" component="h2">
        カタログ（{FEATURE_COUNT} 機能）
      </Typography>
      <Grid container spacing={2}>
        {cards.slice(0, 12).map((C, i) => (
          <Grid key={i} size={{ xs: 12, md: 4 }}>
            <C items={[]} />
          </Grid>
        ))}
      </Grid>
    </Container>
  );
}
