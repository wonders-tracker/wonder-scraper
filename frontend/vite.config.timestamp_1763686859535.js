// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";
var vite_config_default = defineConfig({
  plugins: [react(), tsconfigPaths()],
  server: {
    port: 3e3
  }
});
export {
  vite_config_default as default
};
