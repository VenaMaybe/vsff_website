import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import vueDevTools from 'vite-plugin-vue-devtools'

export default defineConfig({
	plugins: [
		vue(),
		vueDevTools(),
	],
	resolve: {
		alias: {
			'@': fileURLToPath(
				new URL('./src', import.meta.url),
			),
		},
	},
	server: {
		proxy: {
			// For local development
			'/api': {
				target: 'http://127.0.0.1:5000',
				changeOrigin: true,
			},
			'/socket.io': {
				target: 'http://127.0.0.1:5000',
				changeOrigin: true,
				ws: true, // Proxy WebSocket traffic
			},
		},
	},
})