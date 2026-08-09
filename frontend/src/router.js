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
			path: '/color',
			name: 'color',
			component: ColorExplorerView,
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