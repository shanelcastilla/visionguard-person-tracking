import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: ".next-build",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
