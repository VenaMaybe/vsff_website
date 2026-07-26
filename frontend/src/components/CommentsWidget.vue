<script setup>
import {
	computed,
	nextTick,
	onBeforeUnmount,
	onMounted,
	ref,
	watch,
} from 'vue'

import { io } from 'socket.io-client'

const comments = ref([])
const name = ref('')
const body = ref('')
const error = ref('')
const loading = ref(false)
const posting = ref(false)
const commentsList = ref(null)

// teleporting stuff
const props = defineProps({
	open: {
		type: Boolean,
		default: false,
	},
})

const emit = defineEmits([
	'update:open',
])

const panelOpen = computed({
	get() {
		return props.open
	},

	set(value) {
		emit('update:open', value)
	},
})
// -----

const socket = io('/comments', {
	autoConnect: false,
})

async function scrollToNewest() {
	await nextTick()

	if (!commentsList.value) {
		return
	}

	commentsList.value.scrollTop =
		commentsList.value.scrollHeight
}

watch(panelOpen, async isOpen => {
	if (!isOpen) {
		return
	}

	await nextTick()
	await scrollToNewest()
})

async function addComment(comment) {
	const commentAlreadyExists = comments.value.some(
		existingComment => existingComment.id === comment.id,
	)

	if (commentAlreadyExists) {
		return
	}

	comments.value.push(comment)

	await scrollToNewest()
}

async function loadComments() {
	loading.value = true
	error.value = ''

	try {
		const response = await fetch('/api/comments')
		const data = await response.json()

		if (!response.ok) {
			throw new Error(
				data.error ?? 'Could not load comments.',
			)
		}

		comments.value = data.sort(
			(firstComment, secondComment) =>
				new Date(firstComment.createdAt)
				- new Date(secondComment.createdAt),
		)

		await scrollToNewest()
	} catch (requestError) {
		error.value = requestError.message
	} finally {
		loading.value = false
	}
}

async function postComment() {
	const trimmedName = name.value.trim()
	const trimmedBody = body.value.trim()

	if (!trimmedName || !trimmedBody) {
		error.value = 'Please enter both a name and a comment.'
		return
	}

	if (posting.value) {
		return
	}

	posting.value = true
	error.value = ''

	try {
		const response = await fetch('/api/comments', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({
				name: trimmedName,
				body: trimmedBody,
			}),
		})

		const data = await response.json()

		if (!response.ok) {
			throw new Error(
				data.error ?? 'Could not post comment.',
			)
		}

		await addComment(data)

		body.value = ''
	} catch (requestError) {
		error.value = requestError.message
	} finally {
		posting.value = false
	}
}

function receiveComment(comment) {
	addComment(comment)
}

function receiveVisibilityChange({ id, hidden }) {
	if (hidden) {
		comments.value = comments.value.filter(
			(comment) => comment.id !== id,
		)

		return
	}

	loadComments()
}

onMounted(() => {
	socket.on(
		'comment_created',
		receiveComment,
	)
	
	socket.on(
		'comment_visibility_changed',
		receiveVisibilityChange,
	)

	socket.connect()
	loadComments()
})

onBeforeUnmount(() => {
	socket.off(
		'comment_created',
		receiveComment,
	)

	socket.off(
		'comment_visibility_changed',
		receiveVisibilityChange,
	)

	socket.disconnect()
})
</script>

<template>
	<Teleport
		defer
		:to="
			panelOpen
				? '#comments-expanded-target'
				: '#comments-collapsed-target'
		"
	>
		<section class="comments-widget" :class="{
			'is-collapsed': !panelOpen,
		}">
			<header class="comments-header">
				<div class="comments-heading">
					<div class="online-indicator" aria-hidden="true"></div>

					<div>
						<p class="comments-kicker">
							Comments!!!
						</p>

						<h2>Yap Zone</h2>
					</div>
				</div>

				<div class="comments-header-actions">
					<span class="comments-count">
						{{ comments.length }}
					</span>

					<button class="collapse-button" type="button" :aria-expanded="panelOpen" :aria-label="panelOpen
							? 'Collapse comments'
							: 'Open comments'
						" @click="panelOpen = !panelOpen">
						{{ panelOpen ? '−' : '+' }}
					</button>
				</div>
			</header>

			<div v-show="panelOpen" class="comments-shell">

				<div ref="commentsList" class="comments-list" aria-live="polite">
					<p v-if="loading" class="status-message">
						Loading messages...
					</p>

					<p v-else-if="comments.length === 0" class="status-message">
						No messages yet. Begin the yapping.
					</p>

					<article v-for="comment in comments" :key="comment.id" class="comment">
						<div class="comment-avatar" aria-hidden="true">
							{{
								comment.name
									.trim()
									.charAt(0)
									.toUpperCase() || '?'
							}}
						</div>

						<div class="comment-content">
							<div class="comment-meta">
								<strong>
									{{ comment.name }}
								</strong>

								<time :datetime="comment.createdAt">
									{{
										new Date(
											comment.createdAt,
										).toLocaleString()
									}}
								</time>
							</div>

							<p>{{ comment.body }}</p>
						</div>
					</article>
				</div>

				<form class="comments-composer" @submit.prevent="postComment">
					<div class="composer-top">
						<label class="visually-hidden" for="comment-name">
							Name
						</label>

						<input id="comment-name" v-model="name" class="name-input" type="text" maxlength="30"
							placeholder="Your name" autocomplete="name" required>

						<span class="character-count" :class="{
							'near-limit': body.length >= 225,
						}">
							{{ body.length }}/250
						</span>
					</div>

					<div class="composer-row">
						<label class="visually-hidden" for="comment-body">
							Message
						</label>

						<textarea id="comment-body" v-model="body" rows="2" maxlength="250"
							placeholder="Message the yap zone..." required
							@keydown.enter.exact.prevent="postComment"></textarea>

						<button class="send-button" type="submit" :disabled="posting">
							{{ posting ? '...' : 'Send' }}
						</button>
					</div>

					<div class="composer-footer">
						<p v-if="error" class="error-message">
							{{ error }}
						</p>

						<p class="composer-hint">
							Enter to send · Shift+Enter for a new line
						</p>
					</div>
				</form>
			</div>
		</section>
	</Teleport>
</template>

<style scoped>
.comments-widget {
	min-width: 0;
	overflow: hidden;

	/* border: 1px solid var(--color-border-main); */
	border-radius: 1rem;

	/* background: var(--color-card-background); */
	/* box-shadow: */
	/* 0 1rem 2.5rem var(--color-shadow-card), */
	/* inset 0 1px 0 rgba(244, 202, 201, 0.08); */

	color: var(--color-page-text);
	font-family: "source-serif-4", Georgia, serif;
}

.comments-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 0.75rem;

	min-height: 3.5rem;
	padding: 0.5rem 0.7rem;

	/* border-bottom: 1px solid var(--color-border-soft); */

	/* background: */
	/* linear-gradient( */
	/* 135deg, */
	/* var(--color-surface-soft), */
	/* var(--color-prize-background) */
	/* ); */
}

.comments-heading {
	display: flex;
	align-items: center;
	gap: 0.55rem;
	min-width: 0;
}

.comments-heading h2 {
	margin: 0;

	font-family: "cesso", sans-serif;
	font-size: 1.2rem;
	font-weight: 600;
	line-height: 1.1;
}

.comments-kicker {
	margin: 0 0 0.05rem;

	color: var(--color-text-muted);
	font-size: 0.65rem;
	font-weight: 800;
	letter-spacing: 0.1em;
	line-height: 1.2;
	text-transform: uppercase;
}

.online-indicator {
	flex: 0 0 auto;
	width: 0.65rem;
	height: 0.65rem;

	border-radius: 50%;
	background: var(--color-accent-primary);

	box-shadow:
		0 0 0.6rem var(--color-button-glow-soft);
}

.comments-header-actions {
	display: flex;
	align-items: center;
	gap: 0.4rem;
}

.comments-count {
	display: inline-flex;
	justify-content: center;
	align-items: center;

	min-width: 1.8rem;
	height: 1.8rem;
	padding: 0 0.4rem;

	border-radius: 999px;

	background: var(--color-count-badge-background);
	color: var(--color-accent-primary);

	font-size: 0.75rem;
	font-weight: 800;
}

.collapse-button {
	display: inline-flex;
	justify-content: center;
	align-items: center;

	width: 1.9rem;
	height: 1.9rem;
	padding: 0;

	border: 1px solid var(--color-border-button);
	border-radius: 0.45rem;

	background: var(--color-surface-soft);
	color: var(--color-text-button);

	font: inherit;
	font-size: 1.15rem;
	font-weight: 800;
	cursor: pointer;
}

.collapse-button:hover {
	border-color: var(--color-accent-primary);
	background: var(--color-active-tier-background-end);
}

.collapse-button:focus-visible,
.send-button:focus-visible,
input:focus-visible,
textarea:focus-visible {
	outline: 2px solid var(--color-focus-ring);
	outline-offset: 2px;
}

.comments-shell {
	display: grid;
	grid-template-rows: minmax(0, 1fr) auto;

	height: min(28rem, 70vh);
	min-height: 18rem;
}

.comments-list {
	display: flex;
	flex-direction: column;
	gap: 0.1rem;

	min-height: 0;
	padding: 0.35rem 0.5rem;
	overflow-y: auto;

	/* background: var(--color-prize-background); */

	scrollbar-color:
		var(--color-border-button) var(--color-prize-background);
	scrollbar-width: thin;
}

.status-message {
	margin: auto;
	padding: 1rem;

	color: var(--color-text-muted);
	font-size: 0.9rem;
	text-align: center;
}

.comment {
	display: grid;
	grid-template-columns: 2rem minmax(0, 1fr);
	gap: 0.5rem;

	padding: 0.38rem 0.3rem;
	border-radius: 0.45rem;
}

.comment:hover {
	background: var(--color-table-hover);
}

.comment-avatar {
	display: flex;
	justify-content: center;
	align-items: center;

	width: 2rem;
	height: 2rem;

	border: 1px solid var(--color-border-main);
	border-radius: 50%;

	background: var(--color-count-badge-background);
	color: var(--color-accent-primary);

	font-size: 0.8rem;
	font-weight: 900;
	text-transform: uppercase;
}

.comment-content {
	min-width: 0;
}

.comment-meta {
	display: flex;
	flex-wrap: wrap;
	align-items: baseline;
	gap: 0.35rem;
}

.comment-meta strong {
	color: var(--color-page-text);
	font-size: 0.9rem;
	line-height: 1.2;
}

.comment-meta time {
	color: var(--color-text-muted);
	font-size: 0.65rem;
	line-height: 1.2;
}

.comment p {
	margin: 0.08rem 0 0;

	color: var(--color-text-secondary);
	font-size: 0.9rem;
	line-height: 1.35;

	overflow-wrap: anywhere;
	white-space: pre-wrap;
}

.comments-composer {
	display: grid;
	gap: 0.35rem;

	padding: 0.5rem 0.6rem 0.55rem;

	/* border-top: 1px solid var(--color-border-soft); */
	/* background: var(--color-surface-soft); */
}

.composer-top {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.name-input {
	width: min(10rem, 55%);
}

.character-count {
	margin-left: auto;

	color: var(--color-text-muted);
	font-size: 0.7rem;
	font-variant-numeric: tabular-nums;
}

.character-count.near-limit {
	color: var(--color-error-text);
}

.composer-row {
	display: grid;
	grid-template-columns: minmax(0, 1fr) auto;
	align-items: stretch;
	gap: 0.4rem;
}

input,
textarea {
	box-sizing: border-box;
	width: 100%;

	border: 1px solid var(--color-border-soft);
	border-radius: 0.5rem;

	background: var(--color-prize-background);
	color: var(--color-page-text);

	font: inherit;
	font-size: 0.9rem;
}

input {
	height: 2rem;
	padding: 0 0.55rem;
}

textarea {
	min-height: 2.7rem;
	max-height: 7rem;
	padding: 0.45rem 0.55rem;

	line-height: 1.35;
	resize: vertical;
}

input::placeholder,
textarea::placeholder {
	color: var(--color-text-muted);
	opacity: 0.8;
}

input:focus,
textarea:focus {
	border-color: var(--color-accent-primary);
}

.send-button {
	min-width: 4.25rem;
	padding: 0.4rem 0.75rem;

	border: 0;
	border-radius: 0.5rem;

	background:
		linear-gradient(135deg,
			var(--color-accent-primary),
			var(--color-accent-pink));

	color: var(--color-on-accent);

	font: inherit;
	font-size: 0.82rem;
	font-weight: 800;
	cursor: pointer;
}

.send-button:hover:not(:disabled) {
	filter: brightness(1.06);
}

.send-button:disabled {
	cursor: not-allowed;
	opacity: 0.55;
}

.composer-footer {
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 0.5rem;
	min-height: 1rem;
}

.composer-hint,
.error-message {
	margin: 0;

	font-size: 0.68rem;
	line-height: 1.2;
}

.composer-hint {
	margin-left: auto;
	color: var(--color-text-muted);
}

.error-message {
	color: var(--color-error-text);
}

.visually-hidden {
	position: absolute;

	width: 1px;
	height: 1px;
	padding: 0;
	margin: -1px;
	overflow: hidden;

	clip: rect(0, 0, 0, 0);
	white-space: nowrap;
	border: 0;
}

@media (max-width: 52rem) {
	.comments-header {
		padding: 0.45rem 0.55rem;
	}

	.comments-shell {
		height: min(24rem, 70svh);
		min-height: 17rem;
	}

	.comments-list {
		padding: 0.3rem 0.35rem;
	}

	.comment {
		grid-template-columns: 1.75rem minmax(0, 1fr);
		gap: 0.4rem;
		padding: 0.35rem 0.2rem;
	}

	.comment-avatar {
		width: 1.75rem;
		height: 1.75rem;
	}

	.comments-composer {
		padding: 0.45rem;
	}

	.name-input {
		width: min(9rem, 65%);
	}

	.composer-hint {
		display: none;
	}
}
</style>