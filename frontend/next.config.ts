import type { NextConfig } from "next";

// The backend base URL. Locally defaults to the FastAPI dev server; on Render
// set NEXT_PUBLIC_API_URL to the backend service URL. All client fetches use
// RELATIVE paths (/api, /reports, /exports, /charts) and these rewrites proxy
// them to the backend — so the user only ever needs the frontend URL.
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API}/api/:path*` },
      { source: "/reports/:path*", destination: `${API}/reports/:path*` },
      { source: "/exports/:path*", destination: `${API}/exports/:path*` },
      { source: "/charts/:path*", destination: `${API}/charts/:path*` },
    ];
  },
};

export default nextConfig;
