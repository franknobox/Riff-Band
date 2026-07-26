import type { NextConfig } from "next";

const staticExport = process.env.AI4MS_STATIC_EXPORT === "1";

const nextConfig: NextConfig = staticExport
  ? {
      output: "export",
      trailingSlash: true,
      images: { unoptimized: true },
    }
  : {
      async rewrites() {
        const apiOrigin = (process.env.AI4MS_API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
        return [
          {
            source: "/api/v1/:path*",
            destination: `${apiOrigin}/api/v1/:path*`,
          },
          {
            source: "/healthz",
            destination: `${apiOrigin}/healthz`,
          },
          {
            source: "/docs",
            destination: `${apiOrigin}/docs`,
          },
          {
            source: "/openapi.json",
            destination: `${apiOrigin}/openapi.json`,
          },
        ];
      },
    };

export default nextConfig;
