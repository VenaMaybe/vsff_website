<script setup>
import { ref } from 'vue'
import flyerImage from '@/assets/images/Artboard 1@2x.png'

/* What does this script do?
	Magnifying glass
*/

const flyerLens = ref({
	visible: false,
	expanded: false,
	x: 0,
	y: 0,
	backgroundX: 50,
	backgroundY: 50,
})

const POSITION_STRENGTH = 1.12

function moveFlyerLens(event) {
	const flyer = event.currentTarget
	const rect = flyer.getBoundingClientRect()

	const x = Math.max(
		0,
		Math.min(event.clientX - rect.left, rect.width),
	)

	const y = Math.max(
		0,
		Math.min(event.clientY - rect.top, rect.height),
	)

	const rawBackgroundX = (x / rect.width) * 100
	const rawBackgroundY = (y / rect.height) * 100

	flyerLens.value.visible = true
	flyerLens.value.x = x
	flyerLens.value.y = y

	flyerLens.value.backgroundX =
		50 + (rawBackgroundX - 50) * POSITION_STRENGTH

	flyerLens.value.backgroundY =
		50 + (rawBackgroundY - 50) * POSITION_STRENGTH
	}

function startFlyerLens(event) {
	/*
	 * Immediately place and show the lens where the user touched.
	 */
	moveFlyerLens(event)

	flyerLens.value.expanded = true

	/*
	 * Keep receiving movement and release events even if the
	 * finger slides slightly outside the flyer.
	 */
	event.currentTarget.setPointerCapture(event.pointerId)
}

function stopFlyerLens(event) {
	flyerLens.value.expanded = false

	if (event.currentTarget.hasPointerCapture(event.pointerId)) {
		event.currentTarget.releasePointerCapture(event.pointerId)
	}

	/*
	 * Touchscreens have no hover, so hide the lens after release.
	 * With a mouse, leave it visible until the pointer leaves.
	 */
	if (event.pointerType !== 'mouse') {
		flyerLens.value.visible = false
	}
}

function leaveFlyerLens(event) {
	/*
	 * Only mouse pointers need hover-based hiding.
	 */
	if (event.pointerType === 'mouse' && !flyerLens.value.expanded) {
		flyerLens.value.visible = false
	}
}

defineProps({
	submissionData: {
		type: Object,
		required: true,
	},
	loading: {
		type: Boolean,
		required: true,
	},
	error: {
		type: String,
		required: true,
	},
	lastUpdated: {
		type: String,
		required: true,
	},
	countdown: {
		type: String,
		required: true,
	},
	estimateJudgingDays: {
		type: Number,
		default: 0,
	},
	judgingDaysPerSubmission: {
		type: Number,
		default: 0,
	},
	estimateJudgingEnd: {
		type: Date,
		default: null,
	},
	judgingCountdown: {
		type: String,
		default: '',
	},
	currentPrizePool: {
		type: Number,
		default: 0,
	},
})

const emit = defineEmits([
	'refresh',
])
</script>

<template>
	<div class="styled-page">
		<div
			class="left-decoration"
			aria-hidden="true"
		></div>
		<div
			class="background-flower background-flower--left"
			aria-hidden="true"
		></div>

		<div
			class="background-flower background-flower--right"
			aria-hidden="true"
		></div>
		<main class="container">
			<header class="title hero">
				<p class="eyebrow">
					Writing competition
				</p>

				<h1>Vena"s Short Fiction Fiasco 2!!!</h1>

				<p class="hero-description">
					A lowkey way to force yourself to write, maybe win a prize, and definitely get some critique from your fellow writers!!!
				</p>
			</header>

			<section class="about-section card">
				<div class="about-text">
					<p class="eyebrow">
						Your questionable host
					</p>

					<h2>About Me</h2>

					<p>
						Hi! I'm Vena (crazy I know). I'm a UC Berkeley student (sigh), who, instead of doing engineering homework, spends most of my time making art! I produce music, paint, and love synthesizers and like, a ton of stuff.
					</p>

					<p>
						However, I especially love to read and write fiction—specifically
						science fiction and fantasy, but I like other stuff too.
					</p>

					<p>
						A semester or so ago, I hosted my first writing competition at our local creative writing club with my friends (ya'll) because I'd found my way into $50, and I had always wanted writers, including me, to have a way to make a bit of money from their writing while also getting feedback and sharing it with other ppl!
					</p>

					<p>
						It went great, and we had eight submissions!!! I genuinely loved reading through all of them so much, and each was unique and interesting. So! I'm doing it again, and this time aiming for hopefully at least 15 submissions, with potentially bigger prizes!
					</p>

					<p>
						Also, since I want things to be a bit more unbiased, you guys (people who submit) will be responsible for 50% of the judging. (More deets on the flyer, but don't worry, you'll have plenty of time to read and judge!)
					</p>
				</div>

				<aside class="contact-me">
					<h3>Contact Me</h3>

					<p>
						If you have any questions (that aren't answered by the flyer) or want to talk about synthesizers and rats, please reach out to me at:
					</p>

					<ul>
						<li>
							<strong>Discord:</strong>
							vena.
						</li>

						<li>
							<strong>Instagram:</strong>
							@thatnastyratvena
						</li>

						<li>
							<strong>Email:</strong>

							<a href="mailto:vena@berkeley.edu">
								vena@berkeley.edu
							</a>
						</li>

						<li>
							<strong>Venmo:</strong>
							@VenaMaybe
						</li>
					</ul>
				</aside>
			</section>

			<section class="rights-rules card">
	<div class="rules-text">
		<p class="eyebrow">
			Copyright and submission policy
		</p>

		<h2>Your Rights, My Rules???</h2>

		<p>
			Since I'm not a chud, you, of course, retain all copyrights to anything you submit. Since this is indie, and by no means an official publication, it shouldn't prevent you from submitting your work (or some version of it) to literary magazines that require first publication rights.
		</p>

		<p>
			However!!! By submitting, you give me permission to show your work to
			other VSFF participants because that is necessary for judging.
		</p>

		<p>
			I also may eventually add a section where people can read previous
			submissions, but nothing you submit will appear there without
			your permission.
		</p>

		<p>
			I also have distant ideas about a magazine or actual publication (maybe related to VSFF), but that's so distant... and again, nothing happens to your writing without your permission.
		</p>
	</div>

	<div class="rules-list-section">
		<h3>Submission Rules</h3>

		<ul class="rules-list">
			<li>
				<strong>Original work:</strong>
				Submissions must be original works started after the contest
				begins. No fandom or derivative content.
			</li>

			<li>
				<strong>Your own worlds:</strong>
				Writing connected to your own previous worlds or ideas is tentatively okay, but try and be innovative!
			</li>

			<li>
				<strong>Creative layouts:</strong>
				Interesting layouts and original art is awesome! But, think illustrated book or editorial design—not a comic/manga.
			</li>

			<li>
				<strong>One submission:</strong>
				Only one submission is allowed per person. The entry fee is
				$3 and helps fund half the prize pool.
			</li>

			<li>
				<strong>No generative AI:</strong>
				Pretty much be decent. Don't use AI for anything beyond a dictionary or thesaurus.
			</li>

			<li>
				<strong>Content:</strong>
				Feel free to write nsfw stuff, but like, think about artistic nudity type vibe. Don't insert named irl people.
			</li>
		</ul>
	</div>
	</section>

			<section class="submission-callout card call-to-action">
				<div>
					<p class="eyebrow">
						The important part
					</p>

					<h2>So please: Submit Your Story and Share This Site!!!</h2>

					<p>
						The entry fee is $3, and every additional submission helps
						unlock a larger prize pool.
					</p>
				</div>

				<a
					class="primary-button"
					href="https://docs.google.com/forms/d/e/1FAIpQLScIvnP7h2-n1EtqVee5QYanGt66NhiU11gx7sQxUa-f3VyVdg/viewform?usp=dialog"
					target="_blank"
					rel="noopener noreferrer"
				>
					Open Submission Form
				</a>
			</section>

			<div class="statistics-row">
				<section class="total-submissions card statistic-card">
					<p class="eyebrow">Entries</p>

					<h2>Total Submissions</h2>

					<p class="large-number">
						{{ submissionData.count }}
					</p>

					<p class="muted-text">
						Current stories entered
					</p>
				</section>

				<section class="entry-fee card statistic-card">
					<p class="eyebrow">Cost</p>

					<h2>Entry Fee</h2>

					<p class="large-number">
						$3
					</p>

					<p class="muted-text">
						Per submission
					</p>
				</section>

				<section class="prize-pool card statistic-card">
					<p class="eyebrow">Rewards</p>

					<h2>Prize Pool</h2>

					<p class="large-number">
						{{
							['$0', '$30', '$100', '$200'][
								submissionData.prizeTier
							] ?? '$0'
						}}
					</p>

					<p class="muted-text">
						{{
							submissionData.prizeTier === 0
								? 'Currently locked'
								: `Tier ${submissionData.prizeTier} active`
						}}
					</p>
				</section>
			</div>

			<section class="submissions-close card">
				<p class="eyebrow">
					Submission phase
				</p>

				<h2>Submissions Close In</h2>

				<p
					v-if="countdown"
					class="countdown"
					aria-live="polite"
				>
					{{ countdown }}
				</p>

				<p v-else class="muted-text">
					Loading countdown...
				</p>

				<p
					v-if="submissionData.submissionsClose"
					class="deadline"
				>
					<strong>Submission deadline:</strong>

					<br>

					{{ new Date(submissionData.submissionsClose).toLocaleString() }}
				</p>
			</section>

			<section class="judging-information card">
				<p class="eyebrow">
					Judging phase
				</p>

				<h2>Estimated Judging Information</h2>

				<dl class="information-list">
					<div>
						<dt>Estimated length</dt>

						<dd>
							{{ estimateJudgingDays }} days
						</dd>
					</div>

					<div>
						<dt>Calculation</dt>

						<dd>
							{{ submissionData.count }}
							×
							{{ judgingDaysPerSubmission }}
							days
						</dd>
					</div>

					<div v-if="estimateJudgingEnd">
						<dt>Estimated completion</dt>

						<dd>
							{{ estimateJudgingEnd.toLocaleString() }}
						</dd>
					</div>
				</dl>

				<p
					v-if="judgingCountdown"
					class="judging-countdown"
				>
					{{ judgingCountdown }}
				</p>
			</section>


			<section class="prize-information card">
				<div class="section-heading">
					<div>
						<p class="eyebrow">
							Rewards
						</p>

						<h2>Current Prize Information</h2>
					</div>

					<span class="tier-badge">
						{{
							submissionData.prizeTier === 0
								? 'Locked'
								: `Tier ${submissionData.prizeTier}`
						}}
					</span>
				</div>

				<div
					v-if="submissionData.nextTierRequirement !== 0"
					class="progress-section"
				>
					<div class="progress-labels">
						<span>Next prize tier</span>

						<strong>
							{{ submissionData.count }}/{{ submissionData.nextTierRequirement }}
						</strong>
					</div>

					<div class="progress-track">
						<div
							class="progress-fill"
							:style="{
								width: `${Math.min(
									(
										submissionData.count
										/ submissionData.nextTierRequirement
									) * 100,
									100,
								)}%`,
							}"
						></div>
					</div>

					<p class="muted-text">
						{{
							Math.max(
								submissionData.nextTierRequirement
									- submissionData.count,
								0,
							)
						}}
						more submissions needed for the next tier.
					</p>
				</div>

				<p v-else>
					Highest tier achieved. Vena is not that rich.
				</p>

				<div
					v-if="submissionData.prizeTier === 0"
					class="locked-message"
				>
					<h3>Prize Pool Locked</h3>

					<p>
						There are not enough submissions yet. Please please please WRITE!!! And share the competition with your friends!
					</p>
				</div>

				<div class="prize-grid">
					<article
						class="prize-tier"
						:class="{
							'active-tier': submissionData.prizeTier === 1,
						}"
					>
						<div class="prize-heading">
							<div>
								<p class="tier-label">
									Tier 1
								</p>

								<h3>$30 Prize Pool</h3>
							</div>

							<span
								v-if="submissionData.prizeTier === 1"
								class="current-label"
							>
								Current
							</span>
						</div>

						<table>
							<tbody>
								<tr>
									<td>1st place</td>
									<td>$15</td>
								</tr>

								<tr>
									<td>2nd place</td>
									<td>$10</td>
								</tr>

								<tr>
									<td>3rd place</td>
									<td>$5</td>
								</tr>
							</tbody>
						</table>
					</article>

					<article
						class="prize-tier"
						:class="{
							'active-tier': submissionData.prizeTier === 2,
						}"
					>
						<div class="prize-heading">
							<div>
								<p class="tier-label">
									Tier 2
								</p>

								<h3>$100 Prize Pool</h3>
							</div>

							<span
								v-if="submissionData.prizeTier === 2"
								class="current-label"
							>
								Current
							</span>
						</div>

						<table>
							<tbody>
								<tr>
									<td>1st place</td>
									<td>$50</td>
								</tr>

								<tr>
									<td>2nd–3rd place</td>
									<td>$20 each</td>
								</tr>

								<tr>
									<td>4th–5th place</td>
									<td>$5 each</td>
								</tr>
							</tbody>
						</table>
					</article>

					<article
						class="prize-tier"
						:class="{
							'active-tier': submissionData.prizeTier === 3,
						}"
					>
						<div class="prize-heading">
							<div>
								<p class="tier-label">
									Tier 3
								</p>

								<h3>$200 Prize Pool</h3>
							</div>

							<span
								v-if="submissionData.prizeTier === 3"
								class="current-label"
							>
								Current
							</span>
						</div>

						<table>
							<tbody>
								<tr>
									<td>1st place</td>
									<td>$100</td>
								</tr>

								<tr>
									<td>2nd–3rd place</td>
									<td>$30 each</td>
								</tr>

								<tr>
									<td>4th–7th place</td>
									<td>$10 each</td>
								</tr>
							</tbody>
						</table>
					</article>
				</div>
			</section>

			<section class="submissions-refresh card">
				<div class="section-heading">
					<div>
						<p class="eyebrow">
							Entries
						</p>

						<h2>Current Submissions</h2>
					</div>

					<span class="count-badge">
						{{ submissionData.count }}
					</span>
				</div>

				<!-- <p v-if="loading">
					Refreshing submissions...
				</p> -->

				<p
					v-if="error"
					class="error-message"
				>
					Could not refresh: {{ error }}
				</p>

				<p v-if="submissionData.submissions.length === 0">
					No submissions yet.
				</p>

				<div
					v-else
					class="table-frame"
				>
					<div class="table-scroll">
						<table>
							<thead>
								<tr>
									<th>Author</th>
									<th>Word count</th>
									<th>Submitted at</th>
								</tr>
							</thead>

							<tbody>
								<tr
									v-for="(submission, index) in submissionData.submissions"
									:key="index"
								>
									<td>{{ submission.author }}</td>
									<td>{{ submission.wordCount }}</td>
									<td>{{ submission.submittedAt }}</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>

				<div class="refresh-controls">
					<button
						class="secondary-button"
						type="button"
						:disabled="loading"
						@click="emit('refresh')"
					>
						{{ loading ? 'Refreshing...' : 'Refresh Submissions' }}
					</button>

					<p
						v-if="lastUpdated"
						class="last-updated"
					>
						Last updated: {{ lastUpdated }}
					</p>
				</div>
			</section>

			<section class="flyer-section card">
				<div class="flyer-heading">
					<a
						class="flyer-download secondary-button"
						:href="flyerImage"
						download="VSFF2-flyer-ehehehe.png"
					>
						Download Flyer
					</a>

					<div class="flyer-heading-text">
						<p class="eyebrow">
							All the details
						</p>

						<h2>Current Competition Flyer</h2>
					</div>

					<div
						class="flyer-heading-spacer"
						aria-hidden="true"
					></div>
				</div>

				<div
					class="flyer-link"
					@pointermove="moveFlyerLens"
					@pointerleave="leaveFlyerLens"
					@pointerdown.prevent="startFlyerLens"
					@pointerup="stopFlyerLens"
					@pointercancel="stopFlyerLens"
					@contextmenu.prevent
					@dragstart.prevent
				>
					<img
						class="flyer-image"
						:src="flyerImage"
						alt="Flyer for Vena's Short Fiction Fiasco"
						draggable="false"
					>

					<div
						v-show="flyerLens.visible"
						class="flyer-magnifier"
						:class="{
							'is-expanded': flyerLens.expanded,
						}"
						:style="{
							left: `${flyerLens.x}px`,
							top: `${flyerLens.y}px`,
						}"
					>
						<img
							class="flyer-magnifier-image"
							:src="flyerImage"
							alt=""
							draggable="false"
							:style="{
								transformOrigin:
									`${flyerLens.backgroundX}% ${flyerLens.backgroundY}%`,
							}"
						>
					</div>
				</div>
			</section>
		</main>
	</div>
</template>

<style scoped>
.styled-page {
	/* Page */
	--color-page-background: #221d1c;
	--color-page-glow-left: rgba(228, 143, 136, 0.26);
	--color-page-glow-right: rgba(244, 202, 201, 0.1);
	--color-page-text: #f4cac9;
	--color-transparent: transparent;
	--color-white: #f4cac9;
	--color-on-accent: #221d1c;

	/* Accents */
	--color-accent-primary: #e48f88;
	--color-accent-dark: #c96f69;
	--color-accent-pink: #f0aaa5;

	/* Text */
	--color-text-secondary: #eab8b5;
	--color-text-muted: #c99591;
	--color-text-button: #e48f88;
	--color-tier-label: #d7a5a1;
	--color-tier-badge-text: #f4cac9;
	--color-error-text: #f0aaa5;
	--color-table-header-text: #e48f88;

	/* Backgrounds and surfaces */
	--color-card-background: rgba(45, 37, 36, 0.94);
	--color-surface-soft: #332a29;
	--color-callout-gradient-start: rgba(45, 37, 36, 0.96);
	--color-callout-gradient-end: rgba(59, 44, 42, 0.96);
	--color-countdown-background: #3a2927;
	--color-error-background: #3b2223;
	--color-count-badge-background: #49312f;
	--color-tier-badge-background: #4a302e;
	--color-progress-track: #4a3836;
	--color-prize-background: #2b2423;
	--color-active-tier-background-end: #3a2b29;
	--color-table-header-background: #342928;
	--color-table-hover: #3a2d2b;

	/* Borders */
	--color-border-main: #5a403d;
	--color-border-soft: #4a3634;
	--color-divider: #543b39;
	--color-border-button: #7a514d;
	--color-error-border: #9d5955;
	--color-information-divider: #4a3735;
	--color-locked-border: #8b5f5b;
	--color-prize-border: #5d4441;
	--color-active-tier-border: #e48f88;
	--color-table-border: #4b3735;
	--color-table-row-border: #3f302e;

	/* Hero and button gradients */
	--color-hero-gradient-start: rgba(228, 143, 136, 0.92);
	--color-hero-gradient-end: rgba(181, 92, 86, 0.94);

	/* Shadows and focus */
	--color-shadow-hero: rgba(0, 0, 0, 0.38);
	--color-shadow-card: rgba(0, 0, 0, 0.24);
	--color-shadow-primary-button: rgba(0, 0, 0, 0.28);
	--color-shadow-hero-button: rgba(0, 0, 0, 0.3);
	--color-shadow-active-tier: rgba(228, 143, 136, 0.16);
	--color-focus-ring: rgba(228, 143, 136, 0.4);

	/* Button glow */
	--color-button-glow: rgba(255, 145, 72, 0.55);
	--color-button-glow-soft: rgba(255, 112, 48, 0.3);
	--color-button-glow-hover: rgba(255, 166, 92, 0.8);
	--color-button-glow-hover-soft: rgba(255, 112, 48, 0.45);

	


	position: relative;
	left: 50%;
	width: 100vw;
	min-height: 100vh;
	margin-left: -50vw;
	overflow-x: clip;
	/* background:
		radial-gradient(
			circle at top left,
			var(--color-page-glow-left) 0,
			var(--color-transparent) 35rem
		),
		radial-gradient(
			circle at top right,
			var(--color-page-glow-right) 0,
			var(--color-transparent) 35rem
		),
		var(--color-page-background); */
	background-color: transparent;
	color: var(--color-page-text);
	font-family: "source-serif-4", Georgia, serif;
	/* font-size: clamp(1.1rem, 0.4vw + 1rem, 1.3rem); */
	font-weight: 400;
	font-style: normal;
	line-height: 1.6;
}

.left-decoration {
	position: fixed;
	top: 0;
	left: 0;
	z-index: 0;

	width: min(80vw, 70rem);
	height: 100vh;

	background-image: url("@/assets/images/Left decoration.svg");
	background-repeat: no-repeat;
	background-position: left center;
	background-size: 80% 100%;

	pointer-events: none;

	/*
	 * Give Safari its own composited layer.
	 * This can reduce small movements during toolbar animations.
	 */
	transform: translate3d(0, 0, 0);
	will-change: transform;
}

/* Phones and touchscreen devices only */
@media (hover: none) and (pointer: coarse) {
	.left-decoration {
		/*
		 * Ten percent extra above and below.
		 */
		top: -10lvh;
		height: 120lvh;
	}
}

/* Phones and touchscreen devices only */
@media (hover: none) and (pointer: coarse) {
	.left-decoration {
		/*
		 * Ten percent extra above and below.
		 */
		top: -10lvh;
		height: 120lvh;
	}
}

.container {
	position: relative;
}

/* Titles and headings */
.hero h1,
.card h2,
.card h3 {
	font-family: "cesso", sans-serif;
	font-weight: 600;
	font-style: normal;
}

/* squares */

.styled-page {
	position: relative;
}

/* Magnifying Glass */

.flyer-link {
	position: relative;
	display: block;
	width: fit-content;
	max-width: 100%;
	margin: 0 auto;
	overflow: visible;
	cursor: none;

	border-radius: 1.25rem;

	box-shadow:
		0 1.5rem 3.5rem rgba(0, 0, 0, 0.48),
		0 0.4rem 1rem rgba(0, 0, 0, 0.3),
		0 0 2.5rem rgba(228, 143, 136, 0.18);
}

.flyer-link::before {
	position: absolute;
	inset: 0;
	z-index: 1;

	border: 1px solid var(--color-border-main);
	border-radius: inherit;

	box-shadow:
		inset 0 1px 0 rgba(244, 202, 201, 0.18),
		inset 1px 0 0 rgba(244, 202, 201, 0.08),
		inset -1px -1px 0 rgba(0, 0, 0, 0.35);

	content: "";
	pointer-events: none;
}



.flyer-link * {
	cursor: none;
}

.flyer-magnifier {
	--finger-offset: 0rem;

	position: absolute;
	z-index: 2;
	width: 14rem;
	height: 14rem;
	overflow: hidden;
	border: 2px solid rgba(244, 202, 201, 0.8);
	border-radius: 50%;
	background: var(--color-page-background);
	box-shadow:
		0 1rem 2.5rem rgba(0, 0, 0, 0.55),
		0 0 1.5rem rgba(228, 143, 136, 0.35);

	transform:
		translate(
			-50%,
			calc(-50% - var(--finger-offset))
		);

	pointer-events: none;

	transition:
		width 250ms ease,
		height 250ms ease,
		transform 250ms ease,
		box-shadow 250ms ease;
}

@media (pointer: coarse) {
	.flyer-magnifier {
		--finger-offset: 9rem;
	}

	.flyer-magnifier.is-expanded {
		--finger-offset: 9rem;
	}

}

.flyer-magnifier.is-expanded {
	width: 28rem;
	height: 28rem;
	box-shadow:
		0 1.5rem 4rem rgba(0, 0, 0, 0.62),
		0 0 2.5rem rgba(228, 143, 136, 0.45);
}

.flyer-magnifier-image {
	--flyer-zoom: 11;

	position: absolute;
	top: 50%;
	left: 50%;
	width: 14rem;
	height: auto;
	max-width: none;
	border-radius: 0.2rem;

	transform:
		translate(-50%, -50%)
		scale(var(--flyer-zoom));

	pointer-events: none;
	user-select: none;
}

@media (hover: none) and (pointer: coarse) {
	.flyer-magnifier-image {
		--flyer-zoom: 7;
	}
}

.flyer-image,
.flyer-magnifier-image {
	pointer-events: none;
}

.flyer-link,
.flyer-link img {
	cursor: none;
	user-select: none;
	-webkit-user-select: none;
	-webkit-user-drag: none;
	-webkit-touch-callout: none;
}

.flyer-link {
	touch-action: none;
}

.flyer-download {
	display: inline-flex;
	justify-content: center;
	align-items: center;
	margin-top: 0.8rem;
	padding: 0.45rem 0.8rem;

	border: 1px solid var(--color-border-button);
	border-radius: 999px;

	background: var(--color-surface-soft);
	box-shadow:
		0 0.4rem 1rem rgba(0, 0, 0, 0.28),
		inset 0 1px rgba(244, 202, 201, 0.08);

	color: var(--color-accent-primary);
	font-size: 0.85rem;
	font-weight: 750;
	text-decoration: none;

	transition:
		transform 150ms ease,
		border-color 150ms ease,
		background 150ms ease,
		box-shadow 150ms ease;
}

.flyer-download:hover {
	border-color: var(--color-accent-primary);
	background: #3a2b29;
	box-shadow:
		0 0.55rem 1.25rem rgba(0, 0, 0, 0.34),
		0 0 1rem rgba(228, 143, 136, 0.16);
	transform: translateY(-2px);
}

.flyer-download:active {
	transform: translateY(0);
}

.flyer-download:focus-visible {
	outline: 3px solid var(--color-focus-ring);
	outline-offset: 3px;
}


/* Shared overlay settings */
.styled-page::before,
.styled-page::after {
	position: fixed;
	top: 50%;
	left: 50%;
	pointer-events: none;
	content: "";
	z-index: 9998;
	background-position: center;
	background-repeat: no-repeat;
	background-size: cover;
}

.styled-page::before {
	--overlay-size: clamp(50vmin, 110vw, 180vmin);

	width: var(--overlay-size);
	height: var(--overlay-size);

	background-image: url("@/assets/images/HardLight@2x.png");
	background-position: center;
	background-repeat: no-repeat;
	background-size: cover;

	border: 0;
	content: "";

	transform: translate(-50%, -50%) rotate(45deg);
	mix-blend-mode: hard-light;
}


@media (max-width: 42rem) {
	.styled-page::before {
		--overlay-size: clamp(150vmin, 160vw, 190vmin);

		width: var(--overlay-size);
		height: var(--overlay-size);

		background-size: contain;

		transform: translate(-50%, -50%) rotate(45deg);
		/* opacity: 0.65; */
	}
}

/* Top overlay: Hue */
.styled-page::after {
	inset: 0;
	width: auto;
	height: auto;

	background-image: url("@/assets/images/Hue@2x.png");
	background-position: center;
	background-repeat: no-repeat;
	background-size: 100% 100%;

	filter:
		hue-rotate(5deg) /* shifts the resulting hue */
		/*saturate(1)     reduces RGB intensity */
		/*brightness(1)   darkens slightly */
		/*contrast(1)     restores some separation */
		blur(10px);

	transform: none;
	mix-blend-mode: hue;
	z-index: 9999;
	opacity: 0.7;
}

/* Flowers */

.background-flower {
	position: fixed;
	z-index: 1;
	width: 62rem;
	height: 63rem;
	background-color: transparent;
	background-position: center;
	background-repeat: no-repeat;
	background-size: contain;
	opacity: 0.9;
	pointer-events: none;
}

.background-flower--left {
	top: 35%;
	left: calc(50vw - 38rem - 35rem);
	background-image: url("@/assets/images/Flower 2.svg");
	transform: translateY(-50%) rotate(0deg);
	filter:
		drop-shadow(0 1.5rem 2rem rgba(0, 0, 0, 0.48))
		drop-shadow(0 0.4rem 0.8rem rgba(0, 0, 0, 0.3))
		drop-shadow(0 0 1.5rem rgba(228, 143, 136, 0.18));
}

.background-flower--right {
	top: 60%;
	right: calc(50vw - 38rem - 40rem);
	z-index: 20;
	background-image: url("@/assets/images/Flower 1.svg");
	filter:
		drop-shadow(0 1.5rem 2rem rgba(0, 0, 0, 0.48))
		drop-shadow(0 0.4rem 0.8rem rgba(0, 0, 0, 0.3))
		drop-shadow(0 0 1.5rem rgba(228, 143, 136, 0.18));
	transform: translateY(-50%) rotate(-14deg);
}

/* STATS ROW */

.statistics-row {
	grid-area: stats;
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 1rem;
}

.statistics-row > * {
	grid-area: auto;
}


/* OTHER */
.styled-page * {
	box-sizing: border-box;
}

.styled-page button,
.styled-page a {
	font: inherit;
}

.container {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	grid-template-areas:
		"title title"
		"about rights"
		"callout callout"
		"stats stats"
		"close judging"
		"prize prize"
		"submissions submissions"
		"flyer flyer";
	gap: 1rem;
	width: min(100% - 2rem, 76rem);
	margin: 0 auto;
	padding: 2rem 0 4rem;
}

.title {
	grid-area: title;
}

.about-section {
	grid-area: about;
}

.rights-rules {
	grid-area: rights;
}

.submission-callout {
	grid-area: callout;
}

.submissions-close {
	grid-area: close;
}

.judging-information {
	grid-area: judging;
}

.prize-information {
	grid-area: prize;
}

.submissions-refresh {
	grid-area: submissions;
}

.flyer-section {
	grid-area: flyer;
	position: relative;
	text-align: center;
}

.flyer-heading {
	display: grid;
	grid-template-columns: 1fr auto 1fr;
	grid-template-areas: "download heading spacer";
	align-items: center;
	gap: 1rem;
	margin-bottom: 1.5rem;
}

.flyer-heading-text {
	grid-area: heading;
	text-align: center;
}

.flyer-heading-text .eyebrow {
	margin-bottom: 0.5rem;
}

.flyer-heading-text h2 {
	margin-bottom: 0;
}

.flyer-download {
	grid-area: download;
	justify-self: start;
}

.flyer-download.secondary-button {
	margin-top: 0.2rem;
}

.flyer-heading-spacer {
	grid-area: spacer;
}

.flyer-link {
	position: relative;
	z-index: 10000;

	display: block;
	width: fit-content;
	max-width: 100%;
	margin: 0 auto;
	overflow: visible;
	cursor: none;

	border-radius: 1.25rem;

	box-shadow:
		0 1.5rem 3.5rem rgba(0, 0, 0, 0.48),
		0 0.4rem 1rem rgba(0, 0, 0, 0.3),
		0 0 2.5rem rgba(228, 143, 136, 0.18);
}

.flyer-image {
	display: block;
	width: min(100%, 100%);
	height: auto;
	margin: 0 auto;
	border-radius: inherit;
	box-shadow: 0 1rem 2.5rem rgba(0, 0, 0, 0.35);
}

.hero {
	padding: clamp(1.75rem, 5vw, 3.5rem);
	border: 1px solid var(--color-border-main);
	border-radius: 1.5rem;
	background:
		linear-gradient(
			135deg,
			var(--color-hero-gradient-start),
			var(--color-hero-gradient-end)
		);
	box-shadow: 0 1rem 3rem var(--color-shadow-hero);
	color: var(--color-white);
}

.hero h1 {
	max-width: 58rem;
	margin: 0;
	font-size: clamp(2rem, 6vw, 4rem);
	line-height: 1;
	letter-spacing: -0.045em;
}

.hero-description {
	max-width: 45rem;
	margin: 1.25rem 0 0;
	font-size: clamp(1rem, 2.5vw, 1.2rem);
	line-height: 1.65;
	opacity: 0.92;
}

.card {
	min-width: 0;
	padding: clamp(1.15rem, 3vw, 1.5rem);
	/* border: 1px solid var(--color-border-main); */
	/* border-radius: 1.25rem; */
	/* background: var(--color-card-background); */
	/* box-shadow: 0 0.5rem 1.5rem var(--color-shadow-card); */
	/* backdrop-filter: blur(1rem); */
}

.card h2,
.card h3,
.card p {
	margin-top: 0;
}

.card h2 {
	margin-bottom: 0.9rem;
	font-size: clamp(1.35rem, 4vw, 1.7rem);
	line-height: 1.2;
}

.card p {
	line-height: 1.7;
}

.card .large-number {
	margin: 0;
	line-height: 0.9;
}

.submission-callout {
	position: relative;
	z-index: 10;
	grid-area: callout;
	border: 1px solid var(--color-border-main);
	border-radius: 1.25rem;
	background: var(--color-card-background);
	box-shadow:
		0 1.5rem 3.5rem rgba(0, 0, 0, 0.48),
		0 0.4rem 1rem rgba(0, 0, 0, 0.3),
		0 0 2.5rem rgba(228, 143, 136, 0.18),
		inset 0 1px 0 rgba(244, 202, 201, 0.1);
	backdrop-filter: blur(1rem);
	-webkit-backdrop-filter: blur(1rem);
	transform: translateY(-0.25rem);
	transition:
		transform 200ms ease,
		box-shadow 200ms ease;
}

.submission-callout:hover {
	box-shadow:
		0 1.8rem 4.25rem rgba(0, 0, 0, 0.56),
		0 0.5rem 1.25rem rgba(0, 0, 0, 0.34),
		0 0 3.25rem rgba(228, 143, 136, 0.26),
		inset 0 1px 0 rgba(244, 202, 201, 0.14);
	transform: translateY(-0.4rem);
}

.eyebrow {
	margin: 0 0 0.5rem;
	color: var(--color-accent-primary);
	font-size: 0.75rem;
	font-weight: 800;
	letter-spacing: 0.14em;
	text-transform: uppercase;
}

.hero .eyebrow {
	color: var(--color-white);
	opacity: 0.8;
}

.about-section {
	display: grid;
	grid-template-columns: 1fr;
	grid-template-areas:
		"about-text"
		"contact";
	gap: 1rem;
}

.about-text {
	grid-area: about-text;
}

.contact-me {
	grid-area: contact;
	align-self: end;
	padding: 1rem;
	border: 1px solid var(--color-border-soft);
	border-radius: 1rem;
	background: var(--color-surface-soft);
}

.contact-me p {
	color: var(--color-text-muted);
}

.contact-me ul {
	margin-bottom: 0;
	padding-left: 1.25rem;
	line-height: 1.8;
}

.contact-me a {
	color: var(--color-accent-primary);
	font-weight: 700;
}

.rights-rules {
	display: block;
}

.rules-text {
	max-width: 70rem;
}

.rules-list-section {
	margin-top: 1.5rem;
	padding-top: 1.25rem;
	border-top: 1px solid var(--color-divider);
}
.rules-list-section h3 {
	margin-bottom: 0.75rem;
	color: var(--color-accent-dark);
}

.rules-list {
	display: grid;
	grid-template-columns: 1fr;
	gap: 0.65rem 1.5rem;
	margin: 0;
	padding-left: 1.25rem;
	color: var(--color-text-secondary);
	line-height: 1.6;
}

.rules-list li {
	padding-left: 0.25rem;
}

.rules-list strong {
	color: var(--color-accent-dark);
}

.call-to-action {
	display: flex;
	flex-direction: column;
	align-items: flex-start;
	gap: 1.25rem;
	background:
		linear-gradient(
			135deg,
			var(--color-callout-gradient-start),
			var(--color-callout-gradient-end)
		);
}

.call-to-action p:last-child {
	margin-bottom: 0;
	color: var(--color-text-muted);
	line-height: 1.6;
}

.primary-button,
.secondary-button {
	display: inline-flex;
	justify-content: center;
	align-items: center;
	min-height: 2.75rem;
	padding: 0.7rem 1.05rem;
	border-radius: 0.75rem;
	font-weight: 750;
	text-decoration: none;
	cursor: pointer;
	transition:
		transform 150ms ease,
		box-shadow 150ms ease,
		background 150ms ease;
}

.primary-button {
	border: 0;
	background:
		linear-gradient(
			135deg,
			var(--color-accent-primary),
			var(--color-accent-pink)
		);
	box-shadow: 0 0.5rem 1rem var(--color-shadow-primary-button);
	color: var(--color-on-accent);
}

/* Animation around button */
@property --button-glow-angle {
	syntax: "<angle>";
	initial-value: 0deg;
	inherits: false;
}

.submission-callout .primary-button {
	position: relative;
	isolation: isolate;
	box-shadow:
		0 0.65rem 1.25rem var(--color-shadow-primary-button),
		0 0 1.25rem var(--color-button-glow),
		0 0 3rem var(--color-button-glow-soft);
}

.submission-callout .primary-button::before {
	position: absolute;
	inset: -0.35rem;
	z-index: -1;
	padding: 0.5rem;
	border-radius: calc(0.75rem + 0.35rem);
	background:
		conic-gradient(
			from var(--button-glow-angle),
			transparent 0deg,
			var(--color-button-glow-soft) 55deg,
			var(--color-button-glow) 100deg,
			transparent 155deg,
			transparent 235deg,
			var(--color-button-glow-soft) 290deg,
			transparent 360deg
		);

	-webkit-mask:
		linear-gradient(#000 0 0) content-box,
		linear-gradient(#000 0 0);
	-webkit-mask-composite: xor;

	mask:
		linear-gradient(#000 0 0) content-box,
		linear-gradient(#000 0 0);
	mask-composite: exclude;

	filter: blur(0.45rem);
	opacity: 0.85;
	content: "";
	pointer-events: none;
	animation: submission-button-glow-spin 4s linear infinite;
}

.submission-callout .primary-button:hover {
	box-shadow:
		0 0.65rem 1.25rem var(--color-shadow-primary-button),
		0 0 1.25rem var(--color-button-glow-hover),
		0 0 3rem var(--color-button-glow-hover-soft);
}

.submission-callout .primary-button:hover::before {
	filter: blur(0.6rem);
	opacity: 1;
	animation-duration: 2.5s;
}

@keyframes submission-button-glow-spin {
	to {
		--button-glow-angle: 360deg;
	}
}

@media (prefers-reduced-motion: reduce) {
	.submission-callout .primary-button::before {
		animation: none;
	}
}

.hero .primary-button {
	background: var(--color-surface-soft);
	box-shadow: 0 0.5rem 1.25rem var(--color-shadow-hero-button);
	color: var(--color-accent-primary);
}

.secondary-button {
	border: 1px solid var(--color-border-button);
	background: var(--color-surface-soft);
	color: var(--color-text-button);
}

.secondary-button:hover:not(:disabled) {
	transform: translateY(-2px);
}

.submission-callout .primary-button,
.submission-callout .primary-button:hover {
	transform: none;
}

.primary-button:focus-visible,
.secondary-button:focus-visible {
	outline: 3px solid var(--color-focus-ring);
	outline-offset: 3px;
}

.secondary-button:disabled {
	cursor: not-allowed;
	opacity: 0.55;
}

.statistic-card {
	display: flex;
	flex-direction: column;
}

.large-number {
	margin-bottom: 0.25rem;
	color: var(--color-accent-primary);
	font-size: clamp(3.5rem, 14vw, 5.5rem);
	font-weight: 900;
	line-height: 0.9;
	letter-spacing: -0.05em;
}

.countdown {
	margin-bottom: 0.75rem;
	color: var(--color-accent-primary);
	font-size: clamp(1.25rem, 5vw, 1.75rem);
	font-weight: 800;
	line-height: 1.35;
}

.judging-countdown {
	margin: 1rem 0 0;
	padding: 0.8rem;
	border-radius: 0.75rem;
	background: var(--color-countdown-background);
	color: var(--color-accent-dark);
	font-weight: 750;
	line-height: 1.5;
}

.countdown,
.judging-countdown {
	text-wrap: balance;
}

.deadline,
.last-updated,
.muted-text {
	color: var(--color-text-muted);
	font-size: 0.9rem;
	line-height: 1.5;
}

.error-message {
	padding: 0.75rem;
	border: 1px solid var(--color-error-border);
	border-radius: 0.75rem;
	background: var(--color-error-background);
	color: var(--color-error-text);
}

.information-list {
	display: grid;
	gap: 0.7rem;
	margin: 0;
}

.information-list > div {
	display: flex;
	justify-content: space-between;
	gap: 1rem;
	padding-bottom: 0.7rem;
	border-bottom: 1px solid var(--color-information-divider);
}

.information-list > div:last-child {
	border-bottom: 0;
}

.information-list dt {
	color: var(--color-text-muted);
}

.information-list dd {
	margin: 0;
	font-weight: 750;
	text-align: right;
}

.refresh-card {
	display: flex;
	flex-direction: column;
	align-items: flex-start;
}

.section-heading,
.prize-heading,
.progress-labels {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 1rem;
}

.section-heading {
	margin-bottom: 1rem;
}

.section-heading h2 {
	margin-bottom: 0;
}

.count-badge,
.tier-badge,
.current-label {
	display: inline-flex;
	justify-content: center;
	align-items: center;
	flex-shrink: 0;
	border-radius: 999px;
	font-size: 0.8rem;
	font-weight: 800;
}

.count-badge {
	min-width: 2.25rem;
	min-height: 2.25rem;
	padding: 0.35rem 0.65rem;
	background: var(--color-count-badge-background);
	color: var(--color-accent-dark);
}

.tier-badge {
	padding: 0.4rem 0.7rem;
	background: var(--color-tier-badge-background);
	color: var(--color-tier-badge-text);
}

.progress-section,
.locked-message {
	margin-bottom: 1.25rem;
	padding: 1rem;
	border-radius: 1rem;
	background: var(--color-surface-soft);
}

.progress-section {
	border: 1px solid var(--color-border-soft);
}

.progress-labels {
	margin-bottom: 0.5rem;
}

.progress-track {
	height: 0.75rem;
	overflow: hidden;
	border-radius: 999px;
	background: var(--color-progress-track);
}

.progress-fill {
	height: 100%;
	border-radius: inherit;
	background:
		linear-gradient(
			90deg,
			var(--color-accent-primary),
			var(--color-accent-pink)
		);
	transition: width 300ms ease;
}

.progress-section .muted-text {
	margin: 0.6rem 0 0;
}

.locked-message {
	border: 1px dashed var(--color-locked-border);
}

.locked-message p {
	margin-bottom: 0;
}

.prize-grid {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 1rem;
	margin-top: 1.25rem;
}

.prize-tier {
	min-width: 0;
	padding: 1rem;
	border: 2px solid var(--color-prize-border);
	border-radius: 1rem;
	background: var(--color-prize-background);
	transition:
		transform 150ms ease,
		border-color 150ms ease,
		box-shadow 150ms ease;
}

.prize-tier table {
	margin-top: 1rem;
	border: 1px solid var(--color-table-row-border);
}

.prize-tier td:last-child {
	font-weight: 800;
	text-align: right;
	white-space: nowrap;
}

.tier-label {
	margin-bottom: 0.2rem;
	color: var(--color-tier-label);
	font-size: 0.75rem;
	font-weight: 800;
	letter-spacing: 0.1em;
	text-transform: uppercase;
}

.current-label {
	padding: 0.3rem 0.6rem;
	background: var(--color-accent-primary);
	color: var(--color-on-accent);
}

.active-tier {
	border-color: var(--color-active-tier-border);
	background:
		linear-gradient(
			145deg,
			var(--color-prize-background),
			var(--color-active-tier-background-end)
		);
	box-shadow: 0 0.75rem 1.75rem var(--color-shadow-active-tier);
	font-weight: 700;
	transform: translateY(-0.2rem);
}

.table-frame {
	width: 100%;
	overflow: hidden;

	border: 1px solid var(--color-table-border);
	border-radius: 0.9rem;

	background: var(--color-prize-background);
}

.table-scroll {
	width: 100%;
	overflow-x: auto;
	overscroll-behavior-x: contain;
	-webkit-overflow-scrolling: touch;
}

.table-scroll table {
	width: 100%;
	min-width: 0;
	table-layout: fixed;

	border-collapse: separate;
	border-spacing: 0;
}

.table-scroll th,
.table-scroll td {
	width: calc(100% / 3);
}

/*
 * Match the table header to the rounded outer frame.
 */
.table-scroll thead th:first-child {
	border-top-left-radius: calc(0.9rem - 1px);
}

.table-scroll thead th:last-child {
	border-top-right-radius: calc(0.9rem - 1px);
}

.table-scroll tbody tr:last-child td:first-child {
	border-bottom-left-radius: calc(0.9rem - 1px);
}

.table-scroll tbody tr:last-child td:last-child {
	border-bottom-right-radius: calc(0.9rem - 1px);
}

table {
	width: 100%;
	border-collapse: collapse;
	background: var(--color-prize-background);
	color: var(--color-page-text);
	text-align: left;
}

th,
td {
	padding: 0.75rem;
	border-bottom: 1px solid var(--color-table-row-border);
}

th {
	background: var(--color-table-header-background);
	color: var(--color-table-header-text);
	font-size: 0.8rem;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	white-space: nowrap;
}

tbody tr:last-child td {
	border-bottom: 0;
}

tbody tr:hover {
	background: var(--color-table-hover);
}

.refresh-controls {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 1rem;
	margin-top: 1rem;
}

.refresh-controls p {
	margin: 0;
}

@media (min-width: 42rem) {
	.call-to-action {
		flex-direction: row;
		justify-content: space-between;
		align-items: center;
	}

	.call-to-action .primary-button {
		flex-shrink: 0;
		margin-right: 26px;
	}
}

@media (min-width: 64rem) {
	.about-section {
		grid-template-rows: 1fr auto;
	}

	.rules-list {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
}

@media (max-width: 52rem) {
	.container {
		grid-template-columns: 1fr;
		grid-template-areas:
			"title"
			"about"
			"rights"
			"callout"
			"stats"
			"close"
			"judging"
			"prize"
			"submissions"
			"flyer";

		row-gap: 0.5rem;
		padding-top: 1rem;
	}

	.statistics-row {
		grid-template-columns: 1fr;
		row-gap: 0;
	}

	.statistic-card .large-number {
		margin-bottom: 0.75rem;
	}

	.statistic-card {
		padding-bottom: 0;
	}

	.prize-grid {
		grid-template-columns: 1fr;
	}

	.active-tier {
		transform: none;
	}

	.rules-list {
		grid-template-columns: 1fr;
	}

	.total-submissions,
	.submission-form {
		grid-template-columns: 1fr;
	}

	.total-submissions {
		grid-template-areas:
			"total-eyebrow"
			"total-heading"
			"total-number"
			"total-description";
	}

	.submission-form {
		grid-template-areas:
			"form-eyebrow"
			"form-heading"
			"form-description"
			"form-button";
		row-gap: 0.75rem;
	}

	.submission-form .primary-button {
		justify-self: stretch;
	}

		.table-scroll table {
		min-width: 36rem;
		table-layout: auto;
	}

	.table-scroll th,
	.table-scroll td {
		width: auto;
	}

	.table-scroll th:first-child,
	.table-scroll td:first-child {
		min-width: 10rem;
	}

	.table-scroll th:nth-child(2),
	.table-scroll td:nth-child(2) {
		width: 8rem;
		min-width: 8rem;
	}

	.table-scroll th:nth-child(3),
	.table-scroll td:nth-child(3) {
		min-width: 14rem;
		white-space: nowrap;
	}
	
	.flyer-heading {
		grid-template-columns: 1fr;
		grid-template-areas:
			"heading"
			"download";
		justify-items: center;
		row-gap: 0;
	}

	.flyer-heading-text {
		grid-area: heading;
		text-align: center;
	}

	.flyer-download {
		grid-area: download;
		justify-self: center;
	}

	.flyer-heading-spacer {
		display: none;
	}
}

</style>