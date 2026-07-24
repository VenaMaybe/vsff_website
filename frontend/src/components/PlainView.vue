<script setup>
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
})

const emit = defineEmits([
	'refresh',
])
</script>


<template>
	<main>
		<h1>Vena's Short Fiction Fiasco 2!!!</h1>

		<h2>About Me</h2>

			<p>
				Hi! I'm Vena (crazy I know). I'm a UC Berkeley student (sigh), who, instead of doing engineering homework, spends most of my time making art! I produce music, paint, and love synthesizers and like, a ton of stuff. However, I especially love to read and write fiction (specifically science fiction and fantasy, but I like other stuff too).
			</p>
			<p>
				A semester or so ago, I hosted my first writing competition at our local creative writing club because I'd found my way into $50, and I had always wanted writers, including me, to have a way to try and make a bit of money from their writing, while also getting feedback and sharing it with other people! So, I decided to try and host a contest about writing short fiction with my friends (ya'll). It went great, and we had 8 submissions!!! I genuinely loved reading through all of them so much, and each was unique and interesting. So! I'm doing it again, and this time aiming for hopefully at least 15 submissions, with some possibly bigger prizes! Also, since I want things to be a bit more unbiased, you guys (people who submit) will be responsible for 50% of the judging (more deets on the flyer, but don't worry, you'll have plenty of time to read and judge!)
			</p>
			<p>
				 
			</p>

			<p>
				If you have any questions (that aren't answered by the flyer) or want to talk about synthesizers and rats, please reach out to me at:
			</p>

			<ul>
				<li>Discord: vena.</li>
				<li>Insta: @thatnastyratvena</li>
				<li>Email: vena@berkeley.edu</li>
				<li>Venmo: @VenaMaybe</li>
			</ul>

		<h2>Your Rights, My Rules???</h2>
			<p>
				Since I'm not a chud, you, of course, retain all your copyrights to anything you submit to this contest. And, since it is indie and by no means an official publication, it shouldn't prevent you from submitting whatever you wrote (or some version of it) to other literary magazines, etc, that need first publishing rights. However!!! By submitting, you are giving me the right to show your submission to any other people who have also submitted to a VSFF contest as this is needed for judging to happen. I also do plan on adding a section of the website where anyone can see previous submissions, but this is still in the works, and nothing you submit will appear there until I get your go-ahead. Also, even more distantly, I do have ideas of some sorta magazine or actual publication (maybe related to VSFF)—but that's so distant, and again, nothing happens to your writing without your permission.
			</p>

			<p>
				A few rules? Pretty much be decent. All submissions have to be original works started after the contest has begun and should not be derivatives of other works (i.e. no fandom content). I will say, however, this rule is lax if you're writing something connected to your own previous worlds or ideas. But try and be innovative! You are also encouraged to layout your work interestingly. I love creative uses of InDesign. This can include your own art as part of the piece though it should focused around a written work. Think illustrated book/editorial, not a comic/manga.
			</p>
			<p>
				Only 1 submission per person. A submission costs $3 which will help pay for half the prize pool. Don't use AI for anything more than a dictionary/thesaurus. Feel free to write nsfw stuff, but like, think about artistic nudity type vibe. Don't insert named irl people. Just make something you're proud of, and want to share with me and some fellow writers!
			</p>

		<h2>So please:
			<a
				href="https://docs.google.com/forms/d/e/1FAIpQLScIvnP7h2-n1EtqVee5QYanGt66NhiU11gx7sQxUa-f3VyVdg/viewform?usp=dialog"
				target="_blank"
				rel="noopener noreferrer"
			>
			Submit your story!!!</a>
			And share this site!!!
		</h2>
		
		<p>Total submissions: {{ submissionData.count }}</p>
		
		<p>Entry fee: $3</p>

		<h2>Submissions Close and Judging Starts In:</h2>

		<p v-if="countdown">
			{{ countdown }}
		</p>

		<p v-if="submissionData.submissionsClose">
			Submission Phase Deadline:
			{{ new Date(submissionData.submissionsClose).toLocaleString() }}
		</p>

		<h2>Estimated Judging Information</h2>

		<p>
			Estimated judging length: {{ estimateJudgingDays }} days = {{ submissionData.count }} * {{ JUDGING_DAYS_PER_SUBMISSION }} days
		</p>

		<p v-if="estimateJudgingEnd">
			Estimated judging completion: {{ estimateJudgingEnd.toLocaleString() }}
		</p>

		<p v-if="judgingCountdown">
			Estimated judging completion in: {{ judgingCountdown }}
		</p>


		<p v-if="error">Could not refresh: {{ error }}</p>

		<h2>Current Submissions</h2>
		<p v-if="loading">Refreshing submissions...</p>


		<p v-if="submissionData.submissions.length === 0">No submissions yet.</p>

		<table v-else border="1">
			<thead>
				<tr>
					<th>Author</th>
					<th>Word count</th>
					<th>Submitted at</th>
				</tr>
			</thead>

			<tbody>
				<tr v-for="(submission, index) in submissionData.submissions" :key="index">
					<td>{{ submission.author }}</td>
					<td>{{ submission.wordCount }}</td>
					<td>{{ submission.submittedAt }}</td>
				</tr>
			</tbody>
		</table>

		<button type="button" :disabled="loading" @click="emit('refresh')">
			{{ loading ? 'Refreshing...' : 'Refresh' }}
		</button>

		<p v-if="lastUpdated">Last updated: {{ lastUpdated }}</p>

		<h2>Current Prize Information</h2>

		<p>Current prize tier: {{ submissionData.prizeTier }}</p>

		<div v-if="submissionData.nextTierRequirement !== 0">
			<p>Next tier requirement: {{ submissionData.nextTierRequirement }}</p>
			<p>Progress: {{ submissionData.count }}/{{ submissionData.nextTierRequirement }}</p>
		</div>

		<div v-else>Highest tier achieved (Vena is not that rich)</div>

		<div v-if="submissionData.prizeTier === 0">
			<h2>Prize Pool Locked</h2>
			<p>There are not enough submissions yet. Share the competition with your friends!</p>
		</div>

<component
	:is="submissionData.prizeTier === 1 ? 'strong' : 'div'"
>
	<p>$30 Prize Pool - Tier 1</p>

	<table border="1">
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
</component>

<component
	:is="submissionData.prizeTier === 2 ? 'strong' : 'div'"
>
	<p>$100 Prize Pool - Tier 2</p>

	<table border="1">
		<tbody>
			<tr>
				<td>1st place</td>
				<td>$50</td>
			</tr>

			<tr>
				<td>2nd - 3rd place</td>
				<td>$20</td>
			</tr>

			<tr>
				<td>4th - 5th place</td>
				<td>$5</td>
			</tr>
		</tbody>
	</table>
</component>

<component
	:is="submissionData.prizeTier === 3 ? 'strong' : 'div'"
>
	<p>$200 Prize Pool - Tier 3</p>

	<table border="1">
		<tbody>
			<tr>
				<td>1st place</td>
				<td>$100</td>
			</tr>

			<tr>
				<td>2nd - 3rd place</td>
				<td>$30</td>
			</tr>

			<tr>
				<td>4th - 7th place</td>
				<td>$10</td>
			</tr>
		</tbody>
	</table>
</component>
	</main>
</template>
