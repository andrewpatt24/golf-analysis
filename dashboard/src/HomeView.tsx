import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export type AppMode = "home" | "on-course" | "coach";

interface HomeViewProps {
  onSelect: (mode: Exclude<AppMode, "home">) => void;
}

export default function HomeView({ onSelect }: HomeViewProps) {
  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        bgcolor: "background.default",
        px: 2,
        py: 4,
      }}
    >
      <Stack spacing={1} alignItems="center" sx={{ mb: 5, textAlign: "center" }}>
        <Typography variant="h4" component="h1" fontWeight={600}>
          Golf
        </Typography>
        <Typography variant="body1" color="text.secondary" maxWidth={320}>
          On the course or reviewing at home — pick your mode.
        </Typography>
      </Stack>

      <Stack spacing={2} width="100%" maxWidth={360}>
        <Button
          variant="contained"
          size="large"
          onClick={() => onSelect("on-course")}
          sx={{
            py: 2.5,
            fontSize: "1.125rem",
            fontWeight: 600,
            textTransform: "none",
            borderRadius: 2,
          }}
        >
          On Course
        </Button>
        <Button
          variant="outlined"
          size="large"
          onClick={() => onSelect("coach")}
          sx={{
            py: 2.5,
            fontSize: "1.125rem",
            fontWeight: 600,
            textTransform: "none",
            borderRadius: 2,
          }}
        >
          Coach Analysis
        </Button>
      </Stack>
    </Box>
  );
}
