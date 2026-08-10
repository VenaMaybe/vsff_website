import {
	createRouter,
	createWebHistory,
} from 'vue-router'

import AdminCommentsView from './views/AdminCommentsView.vue'
import HomeView from './views/HomeView.vue'
import ColorExplorerView from './views/ColorExplorerView.vue'

const router = createRouter({
	history: createWebHistory(),
	routes: [
		{
			path: '/',
			name: 'home',
			component: HomeView,
		},
		{
			path: '/admin/comments',
			name: 'admin-comments',
			component: AdminCommentsView,
		},
		{
			path: '/colors',
			name: 'colors',
			component: ColorExplorerView,
		},
		{
			path: '/color',
			redirect: (to) => ({
				name: 'colors',
				query: to.query,
				hash: to.hash,
			}),
		},
		{
			path: '/:pathMatch(.*)*',
			redirect: {
				name: 'home',
			},
		},
	],
})

export default router
