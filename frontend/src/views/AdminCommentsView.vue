<script setup>
import { onMounted, ref } from 'vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

const authenticated = ref(false)
const password = ref('')
const comments = ref([])
const loading = ref(true)
const submitting = ref(false)
const error = ref('')

async function apiRequest(path, options = {}) {
	const response = await fetch(
		`${API_BASE_URL}${path}`,
		{
			credentials: 'include',
			...options,
			headers: {
				'Content-Type': 'application/json',
				...(options.headers ?? {}),
			},
		},
	)

	const data = await response
		.json()
		.catch(() => null)

	if (!response.ok) {
		throw new Error(
			data?.error ?? `Request failed with status ${response.status}.`,
		)
	}

	return data
}

async function checkSession() {
	loading.value = true
	error.value = ''

	try {
		const data = await apiRequest(
			'/api/admin/session',
		)

		authenticated.value = data.authenticated

		if (authenticated.value) {
			await loadComments()
		}
	} catch (requestError) {
		error.value = requestError.message
	} finally {
		loading.value = false
	}
}

async function login() {
	submitting.value = true
	error.value = ''

	try {
		await apiRequest(
			'/api/admin/login',
			{
				method: 'POST',
				body: JSON.stringify({
					password: password.value,
				}),
			},
		)

		password.value = ''
		authenticated.value = true

		await loadComments()
	} catch (requestError) {
		error.value = requestError.message
	} finally {
		submitting.value = false
	}
}

async function logout() {
	error.value = ''

	try {
		await apiRequest(
			'/api/admin/logout',
			{
				method: 'POST',
			},
		)
	} catch (requestError) {
		error.value = requestError.message
		return
	}

	authenticated.value = false
	comments.value = []
}

async function loadComments() {
	error.value = ''

	try {
		comments.value = await apiRequest(
			'/api/admin/comments',
		)
	} catch (requestError) {
		if (
			requestError.message
				.toLowerCase()
				.includes('authentication')
		) {
			authenticated.value = false
		}

		error.value = requestError.message
	}
}

async function setHidden(comment, hidden) {
	error.value = ''

	try {
		const updatedComment = await apiRequest(
			`/api/admin/comments/${comment.id}`,
			{
				method: 'PATCH',
				body: JSON.stringify({
					hidden,
				}),
			},
		)

		const index = comments.value.findIndex(
			(existingComment) => existingComment.id === comment.id,
		)

		if (index !== -1) {
			comments.value[index] = updatedComment
		}
	} catch (requestError) {
		error.value = requestError.message
	}
}

function formatDate(value) {
	if (!value) {
		return ''
	}

	return new Date(value).toLocaleString()
}

onMounted(checkSession)
</script>

<template>
	<main class="admin-comments">
		<h1>Comment moderation</h1>

		<p
			v-if="error"
			class="error"
		>
			{{ error }}
		</p>

		<p v-if="loading">
			Loading...
		</p>

		<form
			v-else-if="!authenticated"
			class="login-form"
			@submit.prevent="login"
		>
			<label for="admin-password">
				Admin password
			</label>

			<input
				id="admin-password"
				v-model="password"
				type="password"
				autocomplete="current-password"
				required
			>

			<button
				type="submit"
				:disabled="submitting"
			>
				{{ submitting ? 'Signing in...' : 'Sign in' }}
			</button>
		</form>

		<section v-else>
			<div class="toolbar">
				<p>
					{{ comments.length }} comments
				</p>

				<div>
					<button
						type="button"
						@click="loadComments"
					>
						Refresh
					</button>

					<button
						type="button"
						@click="logout"
					>
						Log out
					</button>
				</div>
			</div>

			<div class="table-container">
				<table>
					<thead>
						<tr>
							<th>ID</th>
							<th>Date</th>
							<th>Name</th>
							<th>Comment</th>
							<th>IP address</th>
							<th>Status</th>
							<th>Action</th>
						</tr>
					</thead>

					<tbody>
						<tr
							v-for="comment in comments"
							:key="comment.id"
							:class="{
								hidden: comment.hidden,
							}"
						>
							<td>{{ comment.id }}</td>
							<td>
								{{ formatDate(comment.createdAt) }}
							</td>
							<td>{{ comment.name }}</td>
							<td class="comment-body">
								{{ comment.body }}
							</td>
							<td>
								{{ comment.ipAddress ?? 'Unknown' }}
							</td>
							<td>
								{{ comment.hidden ? 'Hidden' : 'Visible' }}
							</td>
							<td>
								<button
									type="button"
									@click="setHidden(
										comment,
										!comment.hidden,
									)"
								>
									{{ comment.hidden ? 'Unhide' : 'Hide' }}
								</button>
							</td>
						</tr>

						<tr v-if="comments.length === 0">
							<td colspan="7">
								No comments found.
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</section>
	</main>
</template>

<style scoped>
.admin-comments {
	box-sizing: border-box;
	margin: 0 auto;
	max-width: 1400px;
	padding: 2rem;
}

.login-form {
	display: grid;
	gap: 0.75rem;
	max-width: 350px;
}

.login-form input,
.login-form button {
	box-sizing: border-box;
	font: inherit;
	padding: 0.6rem;
}

.toolbar {
	align-items: center;
	display: flex;
	justify-content: space-between;
	margin-bottom: 1rem;
}

.toolbar div {
	display: flex;
	gap: 0.5rem;
}

.table-container {
	overflow-x: auto;
}

table {
	border-collapse: collapse;
	width: 100%;
}

th,
td {
	border: 1px solid;
	padding: 0.6rem;
	text-align: left;
	vertical-align: top;
}

.comment-body {
	min-width: 250px;
	white-space: pre-wrap;
}

tr.hidden {
	opacity: 0.55;
}

.error {
	font-weight: bold;
}
</style>