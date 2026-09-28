import type { NextConfig } from "next";

let backendUrl = process.env.BACKEND_API_URL || "http://127.0.0.1:8000";
if (!backendUrl.startsWith("http://") && !backendUrl.startsWith("https://")) {
  backendUrl = `https://${backendUrl}`;
}
backendUrl = backendUrl.replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
