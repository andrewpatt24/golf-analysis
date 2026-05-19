import { createTheme } from "@mui/material/styles";

/**
 * Material-aligned shell (Roboto, elevation, Google-style primary).
 * Components: [MUI Material](https://mui.com/material-ui/) — React implementation of Material Design
 * (guidelines: [Material Design](https://m2.material.io/) / [M3](https://m3.material.io/)).
 */
export const dashboardTheme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#1a73e8" },
    secondary: { main: "#5f6368" },
    error: { main: "#d93025" },
    background: {
      default: "#f8f9fa",
      paper: "#ffffff",
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h1: { fontWeight: 400, fontSize: "1.5rem" },
    h2: { fontWeight: 500, fontSize: "1.25rem" },
    h3: { fontWeight: 500, fontSize: "1.05rem" },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: "0 1px 2px 0 rgb(60 64 67 / 30%), 0 1px 3px 1px rgb(60 64 67 / 15%)",
        },
      },
    },
    MuiPaper: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: ({ theme }) => ({
          border: `1px solid ${theme.palette.divider}`,
        }),
      },
    },
  },
});
