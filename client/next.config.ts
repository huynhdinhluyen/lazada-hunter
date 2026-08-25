import type { NextConfig } from "next";

const BACKEND_INTERNAL_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.INTERNAL_API_URL ||
  "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "lh3.googleusercontent.com",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "*.googleusercontent.com",
        pathname: "/**",
      },
    ],
  },
  async rewrites() {
    return [
      {
        source: "/health",
        destination: `${BACKEND_INTERNAL_URL}/health`,
      },
      {
        source: "/api/v1/:path*",
        destination: `${BACKEND_INTERNAL_URL}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
