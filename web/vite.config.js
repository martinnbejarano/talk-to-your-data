import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Sin proxy contra la API: el backend ya abre CORS y un proxy sería un segundo
// lugar donde la dirección del backend está escrita.
export default defineConfig({
  plugins: [react()],
});
