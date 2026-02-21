import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.API_URL || "http://127.0.0.1:4010"}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
