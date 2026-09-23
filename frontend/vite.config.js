import fs from "fs";
import path from "path";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";

// Socket.IO namespaces are site names. The built app reads its from the page
// boot data (window.site_name); the dev server has no boot data, so it takes the
// bench's default site.
const devSiteName = (() => {
	try {
		return (
			JSON.parse(
				fs.readFileSync(
					path.resolve(__dirname, "../../../sites/common_site_config.json"),
					"utf8",
				),
			).default_site || ""
		);
	} catch {
		return "";
	}
})();

export default defineConfig({
	define: { __DEV_SITE_NAME__: JSON.stringify(devSiteName) },
	plugins: [
		frappeui({
			frontendRoute: "/verp",
		}),
		vue(),
	],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "src"),
		},
	},
	build: {
    minify: 'esbuild',
    reportCompressedSize: false,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) return 'vendor'
        },
      },
    },
  },
	optimizeDeps: {
		// frappe-ui's TextEditor imports icons via unplugin-icons' `~icons/lucide/*`
		// virtual modules, resolved by the lucideIcons() Vite plugin (registered
		// above via frappeui()). That plugin's resolveId/load hooks only run in
		// Vite's normal dev-transform pipeline, not in the esbuild-based
		// optimizeDeps scanner used to prebundle bare imports from node_modules -
		// so scanning frappe-ui with esbuild crashes on those unresolved paths.
		// Excluding it here skips that scan and serves it through the regular
		// pipeline instead, where the virtual modules resolve fine.
		exclude: ["frappe-ui"],
		// The flip side of that exclude: frappe-ui's own CommonJS/UMD dependencies
		// are no longer discovered for prebundling, so the browser gets the raw
		// file and fails on a missing default export (the app never mounts and the
		// console stays empty). List each one explicitly.
		include: ["frappe-ui > feather-icons", "debug"],
	},
});
