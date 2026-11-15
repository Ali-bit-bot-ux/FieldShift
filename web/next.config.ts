import type { NextConfig } from "next";
import path from "node:path";

const projectRoot = path.resolve(process.cwd(), "..");
const config: NextConfig = {
  devIndicators: false,
  poweredByHeader: false,
  turbopack: { root: projectRoot },
  outputFileTracingRoot: projectRoot,
};
export default config;
