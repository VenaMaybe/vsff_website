// use >npm run dev
// to start hte front end

/* Script for:
	Hitting google sheets webapp to see submission count
	Caching submissions count
	Keep track of when event phases will start/end
	Toggling between stylized and unstyled views
	Moves the ui switch to plain view button
	Hits the googlesheets webapp ever 2 minutes
*/

<script setup>
import PlainView from '../components/PlainView.vue'
import StyledView from '../components/StyledView.vue'

import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const STORAGE_KEY = 'vsff-submission-data'
const UPDATED_AT_KEY = 'vsff-submission-updated-at'

// json slop that is returned
const submissionData = ref({
	count: 0,
	prizeTier: 0,
	nextTierRequirement: 0,
	submissionsClose: '',
	submissions: [],
})

// variables
const JUDGING_DAYS_PER_SUBMISSION = 1.5
const MILLISECONDS_PER_DAY = 24 * 60 * 60 * 1000
let countdownInterval = null // seconds at a time
const VIEW_MODE_KEY = 'vsff-view-mode'
const SUBMISSION_REFRESH_MILLISECONDS = 2 * 60 * 1000
let submissionRefreshInterval = null

// ui variables
const viewToggleHidden = ref(false)

// live updatable thingies
const loading = ref(false)
const error = ref('')
const lastUpdated = ref('')
const countdown = ref('') // string printed to site
const judgingCountdown = ref('') // string printed to site
const styledView = ref(true)

function handleScroll() {
	viewToggleHidden.value = window.scrollY > 20
}

function updateDocumentTheme() {
	document.documentElement.classList.toggle(
		'styled-view-active',
		styledView.value,
	)

	document.body.classList.toggle(
		'styled-view-active',
		styledView.value,
	)
}

function loadCachedSubmissions() {
	const cachedData = localStorage.getItem(STORAGE_KEY)
	const cachedUpdatedAt = localStorage.getItem(UPDATED_AT_KEY)

	if (!cachedData) {
		return false
	}

	try {
		submissionData.value = JSON.parse(cachedData)
		lastUpdated.value = cachedUpdatedAt ?? ''
		return true
	} catch {
		localStorage.removeItem(STORAGE_KEY)
		localStorage.removeItem(UPDATED_AT_KEY)
		return false
	}
}

function saveSubmissions(data) {
	const updatedAt = new Date().toLocaleString()

	localStorage.setItem(STORAGE_KEY, JSON.stringify(data))

	localStorage.setItem(UPDATED_AT_KEY, updatedAt)

	lastUpdated.value = updatedAt
}

async function fetchSubmissions() {
	if (loading.value) {
		return
	}

	loading.value = true
	error.value = ''

	try {
		const response = await fetch('/api/submissions')

		if (!response.ok) {
			throw new Error(`Request failed with status ${response.status}`)
		}

		const data = await response.json()

		submissionData.value = data
		saveSubmissions(data)
		updateCountdowns() // estimate updates right away too
	} catch (requestError) {
		error.value = requestError.message
	} finally {
		loading.value = false
	}
}

function formatRemainingTime(remainingMilliseconds) {
	const totalSeconds = Math.floor(remainingMilliseconds / 1000)

	const days = Math.floor(totalSeconds / 86400)
	const hours = Math.floor((totalSeconds % 86400) / 3600)
	const minutes = Math.floor((totalSeconds % 3600) / 60)
	const seconds = totalSeconds % 60

	return `${days}\u00A0days, ${hours}\u00A0hours, `
	+ `${minutes}\u00A0minutes, ${seconds}\u00A0seconds`
}

const estimateJudgingDays = computed(() => { // when subData count changes, recalculate this
	return submissionData.value.count * JUDGING_DAYS_PER_SUBMISSION
})

const estimateJudgingEnd = computed(() => {
	if (!submissionData.value.submissionsClose) {
		return null
	}

	const judgingStartMilliseconds = new Date(
		submissionData.value.submissionsClose,
	).getTime()

	if (Number.isNaN(judgingStartMilliseconds)) {
		return null
	}

	const judgingLengthMilliseconds = 
		estimateJudgingDays.value * MILLISECONDS_PER_DAY
	
	return new Date(
		judgingStartMilliseconds + judgingLengthMilliseconds
	)
})

// computed val that updates
const currentPrizePool = computed(() => {
	const prizePoolsByTier = {
		0: 0,
		1: 30,
		2: 100,
		3: 200,
	}

	return prizePoolsByTier[submissionData.value.prizeTier] ?? 0
})

// updates both countdowns
function updateCountdowns() {
	if (!submissionData.value.submissionsClose) {
		countdown.value = ''
		judgingCountdown.value = ''
		return
	}

	const submissionsCloseMilliseconds = new Date(
		submissionData.value.submissionsClose,
	).getTime()

	if (Number.isNaN(submissionsCloseMilliseconds)) {
		countdown.value = 'Invalid submission deadline.'
		judgingCountdown.value = ''
		return
	}

	const now = Date.now()

	const submissionMillisecondsRemaining = submissionsCloseMilliseconds - now

	if (submissionMillisecondsRemaining > 0) {
		countdown.value = formatRemainingTime(
			submissionMillisecondsRemaining,
		)
	} else {
		countdown.value = 'Submissions are closed.'
	}

	if (estimateJudgingEnd.value === null) {
		judgingCountdown.value = ''
		return
	}

	const judgingEndMilliseconds = estimateJudgingEnd.value.getTime()
	const judgingMillisecondsRemaining = judgingEndMilliseconds - now

	if (judgingMillisecondsRemaining > 0) {
		judgingCountdown.value = formatRemainingTime(
			judgingMillisecondsRemaining,
		)
	} else {
		judgingCountdown.value =
			'The estimated judging period is finished.'
	}

	
}

function toggleView() {
	styledView.value = !styledView.value

	localStorage.setItem(
		VIEW_MODE_KEY,
		styledView.value ? 'styled' : 'plain',
	)

	updateDocumentTheme()
}

onMounted(() => {
	const savedViewMode = localStorage.getItem(VIEW_MODE_KEY)

	if (savedViewMode !== null) {
		styledView.value = savedViewMode === 'styled'
	}

	updateDocumentTheme()

	loadCachedSubmissions()
	fetchSubmissions()
	updateCountdowns()

	countdownInterval = setInterval(updateCountdowns, 1000) // update countdown per s

	// Setup interval to hit evry 2 mins
	submissionRefreshInterval = setInterval(() => {
		if (!document.hidden) {
			fetchSubmissions()
		}
	}, SUBMISSION_REFRESH_MILLISECONDS)

	// moves swap button
	viewToggleHidden.value = window.scrollY > 20
	window.addEventListener('scroll', handleScroll, {
		passive: true,
	})
})

onBeforeUnmount(() => { // kill the timer when shit leaves
	if (countdownInterval !== null) {
		clearInterval(countdownInterval)
		countdownInterval = null
	}

	if (submissionRefreshInterval !== null) {
		clearInterval(submissionRefreshInterval)
		submissionRefreshInterval = null
	}

	window.removeEventListener('scroll', handleScroll)
})
</script>

<template>
	<div
		class="app-shell"
		:class="{
			'app-shell--styled': styledView,
		}"
	>
		<button
			class="view-toggle"
			:class="{
				'view-toggle--styled': styledView,
				'view-toggle--hidden': viewToggleHidden,
			}"
			type="button"
			@click="toggleView"
		>
			Switch to {{ styledView ? 'plain' : 'styled' }} view
		</button>

		<StyledView
			v-if="styledView"
			:submission-data="submissionData"
			:loading="loading"
			:error="error"
			:last-updated="lastUpdated"
			:countdown="countdown"
			:estimate-judging-days="estimateJudgingDays"
			:judging-days-per-submission="JUDGING_DAYS_PER_SUBMISSION"
			:estimate-judging-end="estimateJudgingEnd"
			:judging-countdown="judgingCountdown"
			:current-prize-pool="currentPrizePool"
			@refresh="fetchSubmissions"
		/>

		<PlainView
			v-else
			:submission-data="submissionData"
			:loading="loading"
			:error="error"
			:last-updated="lastUpdated"
			:countdown="countdown"
			:estimate-judging-days="estimateJudgingDays"
			:judging-days-per-submission="JUDGING_DAYS_PER_SUBMISSION"
			:estimate-judging-end="estimateJudgingEnd"
			:judging-countdown="judgingCountdown"
			@refresh="fetchSubmissions"
		/>
	</div>
</template>
<style scoped>
/*
	Global layout reset only.

	This does not choose the page theme. It only ensures that the app can
	occupy the full browser height without the browser's default body margin.
*/
/* :global(html),
:global(body) {
	overscroll-behavior-y: none;
} */

:global(html),
:global(body),
:global(#app) {
	min-height: 100%;
	margin: 0;
	background-color: #ffffff;
}

/*
 * Dark background shown behind the styled page,
 * including Safari/macOS overscroll areas.
 */
:global(html.styled-view-active),
:global(body.styled-view-active),
:global(html.styled-view-active #app) {
	background-color: #221d1c;
}

:global(html.styled-view-active),
:global(body.styled-view-active) {
	background:
		radial-gradient(
			circle at top left,
			rgba(228, 143, 136, 0.26) 0,
			transparent 35rem
		),
		radial-gradient(
			circle at top right,
			rgba(244, 202, 201, 0.1) 0,
			transparent 35rem
		),
		#221d1c;

	background-repeat: no-repeat;
}
/*
	The parent shell owns the background for whichever view is active.
	Plain view uses white by default.
*/
.app-shell {
	min-height: 100vh;
	min-height: 100dvh;
}

.app-shell:not(.app-shell--styled) {
	padding: 8px;
	background: #ffffff;
}

/* Applied only while styledView is true */
.app-shell--styled {
	background: #221d1c;
}

/* Basic appearance used in plain view */
.view-toggle {
	position: fixed;
	top: 1rem;
	right: 1rem;
	z-index: 1000;

	/* Mostly normal browser button styling */
	padding: 0.25rem 0.5rem;
	font: inherit;
	cursor: pointer;
}

/* Styled-view appearance */
.view-toggle--styled {
	position: fixed;
	top: 1rem;
	right: 1rem;
	z-index: 1000;
	margin: 0;
	padding: 0.7rem 1rem;
	border: 1px solid #7a514d;
	border-radius: 999px;
	background: rgba(45, 37, 36, 0.9);
	box-shadow:
		0 0.5rem 1.5rem rgba(0, 0, 0, 0.3),
		inset 0 1px rgba(244, 202, 201, 0.08);
	color: #f4cac9;
	font-size: 0.85rem;
	font-weight: 750;
	letter-spacing: 0.02em;
	backdrop-filter: blur(0.75rem);
	cursor: pointer;
	transition:
		transform 150ms ease,
		border-color 150ms ease,
		background 150ms ease,
		box-shadow 150ms ease;
}

.view-toggle--styled:hover {
	border-color: #e48f88;
	background: #3a2b29;
	box-shadow:
		0 0.7rem 1.75rem rgba(0, 0, 0, 0.38),
		0 0 0 1px rgba(228, 143, 136, 0.12);
	color: #e48f88;
	transform: translateY(-2px);
}

.view-toggle {
	transition:
		transform 180ms ease,
		opacity 180ms ease;
}

.view-toggle.view-toggle--hidden {
	opacity: 0;
	pointer-events: none;
	transform: translateX(calc(100% + 2rem));
}

.view-toggle--styled:active {
	transform: translateY(0);
}

.view-toggle--styled:focus-visible {
	outline: 3px solid rgba(228, 143, 136, 0.4);
	outline-offset: 3px;
}

@media (max-width: 36rem) {
	.view-toggle--styled {
		top: 0.65rem;
		right: 0.65rem;
		max-width: calc(100vw - 1.3rem);
		padding: 0.6rem 0.8rem;
		font-size: 0.78rem;
	}
}
</style>