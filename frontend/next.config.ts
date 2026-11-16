import type { NextConfig } from "next";

// The browser talks only to this Next.js origin. Requests to /api/* are forwarded to
// the FastAPI service, so session cookies are first-party and SameSite=Lax applies.
const apiOrigin = process.env.LODGEOS_API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Every LodgeOS screen depends on the signed-in user and is rendered per request, so
  // Cache Components would add complexity without benefit here.
  cacheComponents: false,
  poweredByHeader: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
};

export default nextConfig;
