import { existsSync, readFileSync, statSync, createReadStream } from "node:fs";
import { resolve, join } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

const EXPORTED_DATA_DIR = process.env.EXPORTED_DATA_DIR || "/app/exported_data";
const EXPORTED_PREFIXES = [
  "providers/",
  "inward/",
  "lad/",
  "outward.json",
  "sis_schema.json",
  "tiles/",
];

function serveExportedData(): import("vite").Plugin {
  return {
    name: "serve-exported-data",
    configureServer(server) {
      const base = "/data/";
      server.middlewares.use((req, res, next) => {
        if (!req.url?.startsWith(base)) return next();
        const relPath = decodeURIComponent(req.url.slice(base.length));
        if (
          !EXPORTED_PREFIXES.some((p) => relPath === p || relPath.startsWith(p))
        )
          return next();
        const filePath = resolve(join(EXPORTED_DATA_DIR, relPath));
        if (!filePath.startsWith(resolve(EXPORTED_DATA_DIR))) return next();
        try {
          if (!existsSync(filePath) || !statSync(filePath).isFile())
            return next();

          const isPmtiles = filePath.endsWith(".pmtiles");
          const contentType = isPmtiles
            ? "application/octet-stream"
            : "application/json";

          // PMTiles requires HTTP range requests for efficient tile loading
          const rangeHeader = req.headers.range;
          if (isPmtiles && rangeHeader) {
            const fileSize = statSync(filePath).size;
            const match = rangeHeader.match(/bytes=(\d+)-(\d*)/);
            if (match) {
              const start = parseInt(match[1], 10);
              const end = Math.min(
                match[2] ? parseInt(match[2], 10) : fileSize - 1,
                fileSize - 1,
              );
              res.writeHead(206, {
                "Content-Range": `bytes ${start}-${end}/${fileSize}`,
                "Accept-Ranges": "bytes",
                "Content-Length": end - start + 1,
                "Content-Type": contentType,
              });
              createReadStream(filePath, { start, end }).pipe(res);
              return;
            }
          }

          const content = readFileSync(filePath);
          res.setHeader("Content-Type", contentType);
          res.end(content);
        } catch {
          next();
        }
      });
    },
  };
}

export default defineConfig({
  base: "/",
  plugins: [serveExportedData(), react(), tailwindcss()],
  resolve: {
    alias: [
      { find: /^@(?=\/)/, replacement: path.resolve(__dirname, "./src") },
      {
        find: "posthog-js/react",
        replacement: path.resolve(
          __dirname,
          "../../node_modules/posthog-js/react/dist/esm/index.js",
        ),
      },
    ],
    conditions: ["source"],
  },
  server: {
    host: true,
    watch: {
      usePolling: true,
    },
    proxy: {
      "/api/spatial-query": {
        target: "http://spatial-index-service:3001",
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 600,
  },
});
