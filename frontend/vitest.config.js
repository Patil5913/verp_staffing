import path from "path";
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";

// Kept separate from vite.config.js: the frappe-ui plugin there needs a running bench.
export default defineConfig({
	plugins: [vue()],
	resolve: {
		alias: [
			{ find: /^~icons\/.*/, replacement: path.resolve(__dirname, "tests/support/iconStub.js") },
			{ find: "@", replacement: path.resolve(__dirname, "src") },
		],
	},
	test: {
		environment: "jsdom",
		globals: true,
		include: ["tests/**/*.test.js"],
	},
});
