import * as THREE from 'three'

// Flight feel tuning. These are intentionally kept together so the
// glide can be adjusted without digging through the controller logic.
export const FLIGHT_TUNING = {
	initialSpeed: 0.3,
	cruiseSpeed: 0.35,
	diveSpeedBonus: 1.4,
	boostForwardSpeedBonus: 1.1,
	baseTurnRate: 0.7,
	speedTurnRate: 0.04,
	// Independent steering multipliers; 1 is the original response.
	yawSensitivity: 0.55,
	pitchSensitivity: 0.55,
	rollSensitivity: 0.45,
	maximumPitch: 0.96,
	maximumBank: 0.5,
	bankResponse: 2.8,
	passiveSink: 0.035,
	velocityResponse: 1.5,
	accelerationResponse: 0.9,
	decelerationResponse: 0.45,
	defaultJoystickSensitivity: 0.5,
	minimumFlightFov: 82,
	boostFovIncrease: 14,
	fovResponse: 2.5,

	// Procedural wind audio; no downloaded sound file is required.
	windMasterVolume: 1,
	windBaseVolume: 0.035,
	windSpeedVolume: 0.22,
	windDiveVolume: 0.14,
	windBoostVolume: 0.18,
	windProximityVolume: 0.2,
	windBaseFrequency: 900,
	windSpeedFrequency: 3000,
	windDiveFrequency: 1200,
	windProximityFrequency: 1600,
	windGainEnvelope: 0.65,
	windFilterEnvelope: 0.8,
	windStopEnvelope: 0.6,
}

const WORLD_UP =
	new THREE.Vector3(0, 1, 0)

const FORWARD_FALLBACK =
	new THREE.Vector3(0, 0, -1)

function isAppleTouchDevice() {
	return (
		/iPad|iPhone|iPod/.test(
			navigator.userAgent,
		) ||
		(
			navigator.platform ===
				'MacIntel' &&
			navigator.maxTouchPoints > 1
		)
	)
}

function createSilentWavUrl() {
	const sampleRate = 8000
	const sampleCount = sampleRate
	const bytesPerSample = 2
	const dataLength =
		sampleCount * bytesPerSample
	const buffer =
		new ArrayBuffer(
			44 + dataLength,
		)
	const view =
		new DataView(buffer)

	function writeText(
		offset,
		text,
	) {
		for (
			let index = 0;
			index < text.length;
			index += 1
		) {
			view.setUint8(
				offset + index,
				text.charCodeAt(index),
			)
		}
	}

	writeText(0, 'RIFF')
	view.setUint32(
		4,
		36 + dataLength,
		true,
	)
	writeText(8, 'WAVE')
	writeText(12, 'fmt ')
	view.setUint32(16, 16, true)
	view.setUint16(20, 1, true)
	view.setUint16(22, 1, true)
	view.setUint32(24, sampleRate, true)
	view.setUint32(
		28,
		sampleRate * bytesPerSample,
		true,
	)
	view.setUint16(
		32,
		bytesPerSample,
		true,
	)
	view.setUint16(34, 16, true)
	writeText(36, 'data')
	view.setUint32(
		40,
		dataLength,
		true,
	)

	return URL.createObjectURL(
		new Blob(
			[buffer],
			{
				type: 'audio/wav',
			},
		),
	)
}

function clamp(
	value,
	minimum,
	maximum,
) {
	return Math.min(
		maximum,
		Math.max(
			minimum,
			value,
		),
	)
}

export class ColorExplorerFlightController {
	constructor({
		camera,
		onExit,
	}) {
		this.camera = camera
		this.onExit = onExit
		this.active = false
		this.keys = new Set()
		this.joystickX = 0
		this.joystickY = 0
		this.touchBoosting = false
		this.joystickSensitivity =
			FLIGHT_TUNING.defaultJoystickSensitivity
		this.windVolume = 1
		this.speed =
			FLIGHT_TUNING.initialSpeed
		this.bank = 0
		this.proximity = 0
		this.direction =
			new THREE.Vector3()
		this.velocity =
			new THREE.Vector3()
		this.right =
			new THREE.Vector3()
		this.glideDirection =
			new THREE.Vector3()
		this.desiredVelocity =
			new THREE.Vector3()
		this.lookTarget =
			new THREE.Vector3()
		this.audioContext = null
		this.windSource = null
		this.windGain = null
		this.windFilter = null
		this.mediaUnlockAudio = null
		this.mediaUnlockUrl = null

		this.handleKeyDown =
			this.handleKeyDown.bind(this)
		this.handleKeyUp =
			this.handleKeyUp.bind(this)
		this.handleBlur =
			this.handleBlur.bind(this)

		window.addEventListener(
			'keydown',
			this.handleKeyDown,
		)
		window.addEventListener(
			'keyup',
			this.handleKeyUp,
		)
		window.addEventListener(
			'blur',
			this.handleBlur,
		)
	}

	setCamera(
		camera,
	) {
		this.camera = camera
	}

	start(
		target,
	) {
		if (
			!this.camera
		) {
			return
		}

		this.active = true
		this.keys.clear()
		this.joystickX = 0
		this.joystickY = 0
		this.touchBoosting = false
		this.bank = 0

		if (
			target
		) {
			this.direction
				.copy(target)
				.sub(
					this.camera.position,
				)
		}

		if (
			this.direction.lengthSq() <
				0.000001
		) {
			this.camera.getWorldDirection(
				this.direction,
			)
		}

		if (
			this.direction.lengthSq() <
				0.000001
		) {
			this.direction.copy(
				FORWARD_FALLBACK,
			)
		}

		this.direction.normalize()
		this.speed =
			FLIGHT_TUNING.initialSpeed
		this.velocity
			.copy(
				this.direction,
			)
			.multiplyScalar(
				this.speed,
			)

		this.primeAudio()
	}

	stop() {
		this.active = false
		this.keys.clear()
		this.joystickX = 0
		this.joystickY = 0
		this.touchBoosting = false
		this.mediaUnlockAudio?.pause()

		if (
			this.windGain &&
			this.audioContext
		) {
			this.windGain.gain
				.setTargetAtTime(
					0.0001,
					this.audioContext.currentTime,
					FLIGHT_TUNING
						.windStopEnvelope,
				)
		}
	}

	setJoystick(
		x,
		y,
	) {
		this.joystickX =
			clamp(x, -1, 1)
		this.joystickY =
			clamp(y, -1, 1)
	}

	setJoystickSensitivity(
		sensitivity,
	) {
		this.joystickSensitivity =
			clamp(
				sensitivity,
				0.1,
				2,
			)
	}

	setWindVolume(
		volume,
	) {
		this.windVolume =
			clamp(
				volume,
				0,
				1,
			)
	}

	setBoosting(
		boosting,
	) {
		this.touchBoosting =
			Boolean(boosting)

		if (
			boosting
		) {
			this.primeAudio()
		}
	}

	setProximity(
		proximity,
	) {
		this.proximity =
			clamp(proximity, 0, 1)
	}

	getDirection(
		target = new THREE.Vector3(),
	) {
		return target.copy(
			this.direction,
		)
	}

	isBoosting() {
		return this.touchBoosting ||
			this.keys.has('Space')
	}

	update(
		deltaSeconds,
	) {
		if (
			!this.active ||
			!this.camera
		) {
			return {
				speed: 0,
				dive: 0,
				boosting: false,
				pitch: 0,
				roll: 0,
			}
		}

		const delta =
			clamp(
				deltaSeconds,
				0,
				0.05,
			)
		const keyboardX =
			(
				this.keys.has('KeyD') ||
				this.keys.has('ArrowRight')
					? 1
					: 0
			) -
			(
				this.keys.has('KeyA') ||
				this.keys.has('ArrowLeft')
					? 1
					: 0
			)
		const keyboardY =
			(
				this.keys.has('KeyW') ||
				this.keys.has('ArrowUp')
					? 1
					: 0
			) -
			(
				this.keys.has('KeyS') ||
				this.keys.has('ArrowDown')
					? 1
					: 0
			)
		const steerX =
			clamp(
				keyboardX +
					this.joystickX *
						this.joystickSensitivity,
				-1,
				1,
			)
		const steerY =
			clamp(
				keyboardY +
					this.joystickY *
						this.joystickSensitivity,
				-1,
				1,
			)
		const turnRate =
			FLIGHT_TUNING.baseTurnRate +
				Math.min(
					this.speed,
					3,
				) *
					FLIGHT_TUNING.speedTurnRate

		this.direction.applyAxisAngle(
			WORLD_UP,
			-steerX *
				turnRate *
				FLIGHT_TUNING.yawSensitivity *
				delta,
		)

		this.right.crossVectors(
			this.direction,
			WORLD_UP,
		)

		if (
			this.right.lengthSq() <
				0.000001
		) {
			this.right.set(1, 0, 0)
		} else {
			this.right.normalize()
		}

		this.direction.applyAxisAngle(
			this.right,
			steerY *
				turnRate *
				FLIGHT_TUNING.pitchSensitivity *
				delta,
		)

		if (
			Math.abs(
				this.direction.y,
			) > FLIGHT_TUNING.maximumPitch
		) {
			const horizontalScale =
				Math.sqrt(
					1 -
						FLIGHT_TUNING.maximumPitch *
							FLIGHT_TUNING.maximumPitch,
				)
			const horizontalLength =
				Math.hypot(
					this.direction.x,
					this.direction.z,
				) || 1

			this.direction.x =
				this.direction.x /
					horizontalLength *
					horizontalScale
			this.direction.z =
				this.direction.z /
					horizontalLength *
					horizontalScale
			this.direction.y =
				Math.sign(
					this.direction.y,
				) *
					FLIGHT_TUNING.maximumPitch
		}

		this.direction.normalize()

		const boosting =
			this.isBoosting()
		const dive =
			clamp(
				-this.direction.y,
				0,
				1,
			)
		const targetSpeed =
			FLIGHT_TUNING.cruiseSpeed +
				dive *
					FLIGHT_TUNING.diveSpeedBonus +
				(
					boosting
						? FLIGHT_TUNING
							.boostForwardSpeedBonus
						: 0
				)
		const speedResponse =
			targetSpeed > this.speed
				? FLIGHT_TUNING
					.accelerationResponse
				: FLIGHT_TUNING
					.decelerationResponse

		this.speed +=
			(
				targetSpeed -
				this.speed
			) *
			(
				1 -
				Math.exp(
					-speedResponse * delta,
				)
			)

		this.glideDirection.copy(
			this.direction,
		)
		this.glideDirection.y -=
			FLIGHT_TUNING.passiveSink *
				(
					1 -
					Math.max(
						this.direction.y,
						0,
					)
				)
		this.glideDirection.normalize()

		this.desiredVelocity
			.copy(
				this.glideDirection,
			)
			.multiplyScalar(
				this.speed,
			)

		this.velocity.lerp(
			this.desiredVelocity,
			1 -
				Math.exp(
					-FLIGHT_TUNING
						.velocityResponse *
						delta,
				),
		)

		this.camera.position.addScaledVector(
			this.velocity,
			delta,
		)

		const targetBank =
			-steerX *
				FLIGHT_TUNING.maximumBank *
				FLIGHT_TUNING.rollSensitivity

		this.bank +=
			(
				targetBank -
				this.bank
			) *
			(
				1 -
				Math.exp(
					-FLIGHT_TUNING
						.bankResponse *
						delta,
				)
			)

		this.camera.up.copy(
			WORLD_UP,
		)
		this.lookTarget
			.copy(
				this.camera.position,
			)
			.add(
				this.direction,
			)
		this.camera.lookAt(
			this.lookTarget,
		)
		this.camera.rotateZ(
			this.bank,
		)

		this.updateWindAudio({
			dive,
			boosting,
		})

		return {
			speed:
				this.velocity.length(),
			dive,
			boosting,
			pitch:
				Math.asin(
					clamp(
						this.direction.y,
						-1,
						1,
					),
				),
			roll: this.bank,
		}
	}

	handleKeyDown(
		event,
	) {
		if (
			!this.active
		) {
			return
		}

		if (
			[
				'KeyW',
				'KeyA',
				'KeyS',
				'KeyD',
				'ArrowUp',
				'ArrowDown',
				'ArrowLeft',
				'ArrowRight',
				'Space',
			].includes(
				event.code,
			)
		) {
			event.preventDefault()
			this.primeAudio()
			this.keys.add(
				event.code,
			)
		}

		if (
			event.code ===
				'Escape'
		) {
			event.preventDefault()
			this.onExit?.()
		}
	}

	handleKeyUp(
		event,
	) {
		if (
			!this.active
		) {
			return
		}

		if (
			this.keys.delete(
				event.code,
			)
		) {
			event.preventDefault()
		}
	}

	handleBlur() {
		this.keys.clear()
		this.touchBoosting = false
	}

	primeAudio() {
		this.enableIOSPlaybackAudio()
		this.ensureWindAudio()

		if (
			!this.audioContext ||
			this.audioContext.state ===
				'running'
		) {
			return
		}

		try {
			const resumeResult =
				this.audioContext.resume()

			resumeResult?.catch?.(() => {
				// Another steering or boost gesture will retry.
			})
		} catch {
			// Another steering or boost gesture will retry.
		}
	}

	enableIOSPlaybackAudio() {
		if (
			!isAppleTouchDevice()
		) {
			return
		}

		if (
			navigator.audioSession
		) {
			try {
				navigator.audioSession.type =
					'playback'
				return
			} catch {
				// Older Safari versions need the media-element fallback.
			}
		}

		if (
			!this.mediaUnlockAudio
		) {
			this.mediaUnlockUrl =
				createSilentWavUrl()

			const audio =
				new Audio(
					this.mediaUnlockUrl,
				)

			audio.loop = true
			audio.preload = 'auto'
			audio.volume = 0.01
			audio.setAttribute(
				'playsinline',
				'',
			)
			this.mediaUnlockAudio = audio
		}

		try {
			const playResult =
				this.mediaUnlockAudio.play()

			playResult?.catch?.(() => {
				// Another steering or boost gesture will retry.
			})
		} catch {
			// Another steering or boost gesture will retry.
		}
	}

	ensureWindAudio() {
		if (
			this.audioContext
		) {
			return
		}

		const AudioContextClass =
			window.AudioContext ||
			window.webkitAudioContext

		if (
			!AudioContextClass
		) {
			return
		}

		const context =
			new AudioContextClass()
		const duration = 2
		const buffer =
			context.createBuffer(
				1,
				context.sampleRate * duration,
				context.sampleRate,
			)
		const samples =
			buffer.getChannelData(0)
		let smoothedNoise = 0

		for (
			let index = 0;
			index < samples.length;
			index += 1
		) {
			const whiteNoise =
				Math.random() * 2 - 1

			smoothedNoise =
				smoothedNoise * 0.965 +
					whiteNoise * 0.035
			samples[index] =
				clamp(
					whiteNoise * 0.5 +
						smoothedNoise * 1.8,
					-1,
					1,
				)
		}

		const source =
			context.createBufferSource()
		const filter =
			context.createBiquadFilter()
		const gain =
			context.createGain()

		source.buffer = buffer
		source.loop = true
		filter.type = 'lowpass'
		filter.frequency.value =
			FLIGHT_TUNING.windBaseFrequency
		filter.Q.value = 0.35
		gain.gain.value = 0.0001

		source.connect(filter)
		filter.connect(gain)
		gain.connect(
			context.destination,
		)
		source.start()

		this.audioContext = context
		this.windSource = source
		this.windFilter = filter
		this.windGain = gain
	}

	updateWindAudio({
		dive,
		boosting,
	}) {
		if (
			!this.audioContext ||
			!this.windGain ||
			!this.windFilter
		) {
			return
		}

		const speedLevel =
			clamp(
				(
					this.speed - 0.5
				) / 4,
				0,
				1,
			)
		const windLevel =
			(
				FLIGHT_TUNING.windBaseVolume +
				speedLevel *
					FLIGHT_TUNING.windSpeedVolume +
				dive *
					FLIGHT_TUNING.windDiveVolume +
				this.proximity *
					FLIGHT_TUNING.windProximityVolume +
				(
					boosting
						? FLIGHT_TUNING.windBoostVolume
						: 0
				)
			) *
				FLIGHT_TUNING.windMasterVolume *
				this.windVolume
		const filterFrequency =
			FLIGHT_TUNING.windBaseFrequency +
				speedLevel *
					FLIGHT_TUNING.windSpeedFrequency +
				dive *
					FLIGHT_TUNING.windDiveFrequency +
				this.proximity *
					FLIGHT_TUNING.windProximityFrequency
		const now =
			this.audioContext.currentTime

		this.windGain.gain.setTargetAtTime(
			windLevel,
			now,
			FLIGHT_TUNING
				.windGainEnvelope,
		)
		this.windFilter.frequency
			.setTargetAtTime(
				filterFrequency,
				now,
				FLIGHT_TUNING
					.windFilterEnvelope,
			)
	}

	dispose() {
		this.stop()

		window.removeEventListener(
			'keydown',
			this.handleKeyDown,
		)
		window.removeEventListener(
			'keyup',
			this.handleKeyUp,
		)
		window.removeEventListener(
			'blur',
			this.handleBlur,
		)

		try {
			this.windSource?.stop()
		} catch {
			// The source may already be stopped.
		}

		this.audioContext?.close()
		this.mediaUnlockAudio?.pause()

		if (
			this.mediaUnlockUrl
		) {
			URL.revokeObjectURL(
				this.mediaUnlockUrl,
			)
		}

		this.audioContext = null
		this.windSource = null
		this.windGain = null
		this.windFilter = null
		this.mediaUnlockAudio = null
		this.mediaUnlockUrl = null
	}
}
