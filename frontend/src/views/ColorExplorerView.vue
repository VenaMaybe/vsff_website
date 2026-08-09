<script setup>
import {
	onMounted,
	onBeforeUnmount,
	ref,
} from 'vue'

import * as THREE from 'three'
import {
	OrbitControls,
} from 'three/addons/controls/OrbitControls.js'

import {
	Pane,
} from 'tweakpane'


// Add built-in presets here. Codes can be copied
// from the Color Explorer's "Copy preset code" button.

const DEFAULT_PRESETS = [
	// {
	// 	name: 'Example preset',
	// 	code: 'color-explorer:PASTE_CODE_HERE',
	// },
]


// Vue elements

const threeContainer =
	ref(null)

const paneContainer =
	ref(null)

const utilityPaneContainer =
	ref(null)

const namedPresetContent =
	ref(null)

const pointCountDisplay =
	ref('125,000')

const settingHelp =
	ref(
		'Click a setting name to see what it does.',
	)

const presetEntries =
	ref([])

const newPresetName =
	ref('')

const activePresetName =
	ref('None')

const presetConfirmation =
	ref({
		open: false,
		title: '',
		message: '',
		confirmLabel: '',
		alternateLabel: '',
		danger: false,
	})

let pendingPresetAction = null
let pendingPresetAlternateAction = null


// Three.js stuff

let pane
let utilityPane
let closingColorPickerButton = null
let colorPickerToggleButtons = []
let settingDescriptionLabels = []

let renderer
let animationFrame
let camera
let controls
let material
let pendingCameraState = null

let scene
let geometry
let dots


// Splat sorting stuff

let basePositions
let baseColors
let originalPositions

let sortOrder
let depths

let sortedPositions
let sortedColors

let sortNeeded = true


// Palette Three.js stuff

let paletteGroup = null

let palettePoints = []
let palettePath = []
let paletteSegments = []
let paletteCurve = null

let paletteColorBindings = []
let cylinderGapBinding = null
let cylinderRadiusBinding = null
let cylinderHeightBinding = null
let cubeWidthBinding = null
let cubeHeightBinding = null
let cubeDepthBinding = null
let torusRotationBinding = null
let cameraFovBinding = null
let cameraOrthoSizeBinding = null


// Storage

const CAMERA_STORAGE_KEY =
	'three-camera-state'

const SETTINGS_STORAGE_KEY =
	'color-explorer-settings'

const PRESETS_STORAGE_KEY =
	'color-explorer-presets'

const PANE_STATE_STORAGE_KEY =
	'color-explorer-pane-state'

const LEGACY_DOT_SIZE_STORAGE_KEY =
	'three-dot-size'


// Main settings

const point_density =
	ref(50)

const shape =
	ref('cube')

const renderMode =
	ref('squares')


// Camera settings

const camera_projection =
	ref('perspective')

const camera_fov =
	ref(75)

const camera_ortho_size =
	ref(8)

const camera_near =
	ref(0.1)

const camera_far =
	ref(1000)


// Shape sizes

const cube_width =
	ref(5)

const cube_height =
	ref(5)

const cube_depth =
	ref(5)

const cylinder_gap =
	ref(3)

const cylinder_radius =
	ref(3)

const cylinder_height =
	ref(3)

const TORUS_MAJOR_RADIUS = 3
const TORUS_TUBE_RADIUS = 1.25

const torus_rotation =
	ref(0)


// Palette settings

const MAX_PALETTE_COLORS = 8

const palette_enabled =
	ref(true)

const tunnel_enabled =
	ref(true)

const tunnel_radius =
	ref(0.35)

const palette_size =
	ref(3)

const palette_colors = {
	color1: '#ff4f81',
	color2: '#a855f7',
	color3: '#3b82f6',
	color4: '#22c55e',
	color5: '#facc15',
	color6: '#f97316',
	color7: '#06b6d4',
	color8: '#ffffff',
}

const PALETTE_MARKER_RADIUS =
	0.12

const PALETTE_LINE_RADIUS =
	0.025

const PALETTE_CURVE_SEGMENTS =
	24

const tunnel_influence_scale =
	ref(2.25)

const lattice_relaxation_steps =
	ref(10)

const lattice_repulsion_strength =
	ref(0.18)

const lattice_spring_strength =
	ref(0.35)
	// 10.35 = galaxy

const lattice_restore_strength =
	ref(0.08)


// Dot size

const dot_size =
	ref(0.07)


// Settings persistence

function applySavedNumber(
	target,
	value,
	minimum,
	maximum,
	integer = false,
) {
	if (
		!Number.isFinite(
			value,
		)
	) {
		return
	}

	const normalizedValue =
		integer
			? Math.round(value)
			: value

	target.value =
		THREE.MathUtils.clamp(
			normalizedValue,
			minimum,
			maximum,
		)
}

function applySettings(
	settings,
) {
	if (
		!settings ||
		typeof settings !==
			'object'
	) {
		return false
	}

	if (
		[
			'squares',
			'splats',
		].includes(
			settings.renderMode,
		)
	) {
		renderMode.value =
			settings.renderMode
	}

	if (
		[
			'cube',
			'cylinder',
			'torus',
		].includes(
			settings.shape,
		)
	) {
		shape.value =
			settings.shape
	}

	if (
		[
			'perspective',
			'orthographic',
		].includes(
			settings.cameraProjection,
		)
	) {
		camera_projection.value =
			settings.cameraProjection
	}

	applySavedNumber(
		camera_fov,
		settings.cameraFov,
		10,
		150,
	)

	applySavedNumber(
		camera_ortho_size,
		settings.cameraOrthoSize,
		0.5,
		50,
	)

	applySavedNumber(
		camera_near,
		settings.cameraNear,
		0.001,
		10,
	)

	applySavedNumber(
		camera_far,
		settings.cameraFar,
		10,
		10000,
	)

	applySavedNumber(
		dot_size,
		settings.dotSize,
		0.01,
		1,
	)

	applySavedNumber(
		point_density,
		settings.pointDensity,
		5,
		75,
		true,
	)

	applySavedNumber(
		cube_width,
		settings.cubeWidth,
		0.25,
		12,
	)

	applySavedNumber(
		cube_height,
		settings.cubeHeight,
		0.25,
		12,
	)

	applySavedNumber(
		cube_depth,
		settings.cubeDepth,
		0.25,
		12,
	)

	applySavedNumber(
		cylinder_gap,
		settings.cylinderGap,
		0,
		5,
	)

	applySavedNumber(
		cylinder_radius,
		settings.cylinderRadius,
		0.25,
		10,
	)

	applySavedNumber(
		cylinder_height,
		settings.cylinderHeight,
		0.25,
		12,
	)

	applySavedNumber(
		torus_rotation,
		settings.torusRotation,
		-180,
		180,
	)

	applySavedNumber(
		tunnel_radius,
		settings.tunnelRadius,
		0,
		5,
	)

	applySavedNumber(
		tunnel_influence_scale,
		settings.tunnelInfluenceScale,
		0.25,
		6,
	)

	applySavedNumber(
		lattice_relaxation_steps,
		settings.latticeRelaxationSteps,
		1,
		30,
		true,
	)

	applySavedNumber(
		lattice_repulsion_strength,
		settings.latticeRepulsionStrength,
		0,
		2,
	)

	applySavedNumber(
		lattice_spring_strength,
		settings.latticeSpringStrength,
		0,
		12,
	)

	applySavedNumber(
		lattice_restore_strength,
		settings.latticeRestoreStrength,
		0,
		1,
	)

	applySavedNumber(
		palette_size,
		settings.paletteSize,
		2,
		MAX_PALETTE_COLORS,
		true,
	)

	if (
		typeof settings.paletteEnabled ===
		'boolean'
	) {
		palette_enabled.value =
			settings.paletteEnabled
	}

	if (
		typeof settings.tunnelEnabled ===
		'boolean'
	) {
		tunnel_enabled.value =
			settings.tunnelEnabled
	}

	if (
		settings.paletteColors &&
		typeof settings.paletteColors ===
			'object'
	) {
		for (
			let i = 1;
			i <= MAX_PALETTE_COLORS;
			i++
		) {
			const key =
				`color${i}`

			const color =
				settings.paletteColors[
					key
				]

			if (
				typeof color ===
					'string' &&
				/^#[0-9a-f]{6}$/i
					.test(
						color,
					)
			) {
				palette_colors[key] =
					color
			}
		}
	}

	if (
		isValidCameraState(
			settings.camera,
		)
	) {
		pendingCameraState =
			settings.camera

		if (
			camera &&
			controls
		) {
			applyCameraState(
				pendingCameraState,
			)

			pendingCameraState =
				null
		}
	}

	return true
}

function loadSettings() {
	let savedSettings = null

	try {
		const saved =
			localStorage.getItem(
				SETTINGS_STORAGE_KEY,
			)

		if (
			saved
		) {
			savedSettings =
				JSON.parse(
					saved,
				)
		}
	} catch {
		return
	}

	if (
		!savedSettings ||
		typeof savedSettings !==
			'object'
	) {
		const savedLegacyDotSize =
			localStorage.getItem(
				LEGACY_DOT_SIZE_STORAGE_KEY,
			)

		if (
			savedLegacyDotSize !== null
		) {
			applySavedNumber(
				dot_size,
				Number(
					savedLegacyDotSize,
				),
				0.01,
				1,
			)
		}

		return
	}

	if (
		[
			'squares',
			'splats',
		].includes(
			savedSettings.renderMode,
		)
	) {
		renderMode.value =
			savedSettings.renderMode
	}

	if (
		[
			'cube',
			'cylinder',
			'torus',
		].includes(
			savedSettings.shape,
		)
	) {
		shape.value =
			savedSettings.shape
	}

	if (
		[
			'perspective',
			'orthographic',
		].includes(
			savedSettings.cameraProjection,
		)
	) {
		camera_projection.value =
			savedSettings.cameraProjection
	}

	applySavedNumber(
		camera_fov,
		savedSettings.cameraFov,
		10,
		150,
	)

	applySavedNumber(
		camera_ortho_size,
		savedSettings.cameraOrthoSize,
		0.5,
		50,
	)

	applySavedNumber(
		camera_near,
		savedSettings.cameraNear,
		0.001,
		10,
	)

	applySavedNumber(
		camera_far,
		savedSettings.cameraFar,
		10,
		10000,
	)

	applySavedNumber(
		dot_size,
		savedSettings.dotSize,
		0.01,
		1,
	)

	applySavedNumber(
		point_density,
		savedSettings.pointDensity,
		5,
		75,
		true,
	)

	applySavedNumber(
		cube_width,
		savedSettings.cubeWidth,
		0.25,
		12,
	)

	applySavedNumber(
		cube_height,
		savedSettings.cubeHeight,
		0.25,
		12,
	)

	applySavedNumber(
		cube_depth,
		savedSettings.cubeDepth,
		0.25,
		12,
	)

	applySavedNumber(
		cylinder_gap,
		savedSettings.cylinderGap,
		0,
		5,
	)

	applySavedNumber(
		cylinder_radius,
		savedSettings.cylinderRadius,
		0.25,
		10,
	)

	applySavedNumber(
		cylinder_height,
		savedSettings.cylinderHeight,
		0.25,
		12,
	)

	applySavedNumber(
		torus_rotation,
		savedSettings.torusRotation,
		-180,
		180,
	)

	applySavedNumber(
		tunnel_radius,
		savedSettings.tunnelRadius,
		0,
		5,
	)

	applySavedNumber(
		tunnel_influence_scale,
		savedSettings.tunnelInfluenceScale,
		0.25,
		6,
	)

	applySavedNumber(
		lattice_relaxation_steps,
		savedSettings.latticeRelaxationSteps,
		1,
		30,
		true,
	)

	applySavedNumber(
		lattice_repulsion_strength,
		savedSettings.latticeRepulsionStrength,
		0,
		2,
	)

	applySavedNumber(
		lattice_spring_strength,
		savedSettings.latticeSpringStrength,
		0,
		12,
	)

	applySavedNumber(
		lattice_restore_strength,
		savedSettings.latticeRestoreStrength,
		0,
		1,
	)

	applySavedNumber(
		palette_size,
		savedSettings.paletteSize,
		2,
		MAX_PALETTE_COLORS,
		true,
	)

	if (
		typeof savedSettings.paletteEnabled ===
		'boolean'
	) {
		palette_enabled.value =
			savedSettings.paletteEnabled
	}

	if (
		typeof savedSettings.tunnelEnabled ===
		'boolean'
	) {
		tunnel_enabled.value =
			savedSettings.tunnelEnabled
	}

	if (
		savedSettings.paletteColors &&
		typeof savedSettings.paletteColors ===
			'object'
	) {
		for (
			let i = 1;
			i <= MAX_PALETTE_COLORS;
			i++
		) {
			const key =
				`color${i}`

			const color =
				savedSettings
					.paletteColors[
						key
					]

			if (
				typeof color ===
					'string' &&
				/^#[0-9a-f]{6}$/i
					.test(
						color,
					)
			) {
				palette_colors[key] =
					color
			}
		}
	}

	if (
		isValidCameraState(
			savedSettings.camera,
		)
	) {
		pendingCameraState =
			savedSettings.camera
	}
}

function getCurrentSettings() {
	return {
		renderMode:
			renderMode.value,

		dotSize:
			dot_size.value,

		pointDensity:
			point_density.value,

		shape:
			shape.value,

		cameraProjection:
			camera_projection.value,

		cameraFov:
			camera_fov.value,

		cameraOrthoSize:
			camera_ortho_size.value,

		cameraNear:
			camera_near.value,

		cameraFar:
			camera_far.value,

		camera:
			getCurrentCameraState(),

		cubeWidth:
			cube_width.value,

		cubeHeight:
			cube_height.value,

		cubeDepth:
			cube_depth.value,

		cylinderGap:
			cylinder_gap.value,

		cylinderRadius:
			cylinder_radius.value,

		cylinderHeight:
			cylinder_height.value,

		torusRotation:
			torus_rotation.value,

		paletteEnabled:
			palette_enabled.value,

		tunnelEnabled:
			tunnel_enabled.value,

		tunnelRadius:
			tunnel_radius.value,

		tunnelInfluenceScale:
			tunnel_influence_scale.value,

		latticeRelaxationSteps:
			lattice_relaxation_steps.value,

		latticeRepulsionStrength:
			lattice_repulsion_strength.value,

		latticeSpringStrength:
			lattice_spring_strength.value,

		latticeRestoreStrength:
			lattice_restore_strength.value,

		paletteSize:
			palette_size.value,

		paletteColors: {
			...palette_colors,
		},
	}
}

function getDefaultPresetSettings() {
	return {
		renderMode: 'squares',
		dotSize: 0.07,
		pointDensity: 50,
		shape: 'cube',
		cameraProjection: 'perspective',
		cameraFov: 75,
		cameraOrthoSize: 8,
		cameraNear: 0.1,
		cameraFar: 1000,

		camera: {
			position: {
				x: 0,
				y: 0,
				z: 8,
			},

			target: {
				x: 0,
				y: 0,
				z: 0,
			},

			zoom: 1,
		},

		cubeWidth: 5,
		cubeHeight: 5,
		cubeDepth: 5,
		cylinderGap: 3,
		cylinderRadius: 3,
		cylinderHeight: 3,
		torusRotation: 0,
		paletteEnabled: true,
		tunnelEnabled: true,
		tunnelRadius: 0.35,
		tunnelInfluenceScale: 2.25,
		latticeRelaxationSteps: 10,
		latticeRepulsionStrength: 0.18,
		latticeSpringStrength: 0.35,
		latticeRestoreStrength: 0.08,
		paletteSize: 3,

		paletteColors: {
			color1: '#ff4f81',
			color2: '#a855f7',
			color3: '#3b82f6',
			color4: '#22c55e',
			color5: '#facc15',
			color6: '#f97316',
			color7: '#06b6d4',
			color8: '#ffffff',
		},
	}
}

function fillPresetDefaults(
	settings,
) {
	if (
		!settings ||
		typeof settings !==
			'object'
	) {
		return null
	}

	const defaults =
		getDefaultPresetSettings()

	return {
		...defaults,
		...settings,

		camera:
			isValidCameraState(
				settings.camera,
			)
				? settings.camera
				: defaults.camera,

		paletteColors: {
			...defaults.paletteColors,
			...(
				settings.paletteColors &&
				typeof settings.paletteColors ===
					'object'
					? settings.paletteColors
					: {}
			),
		},
	}
}

function saveSettings() {
	try {
		localStorage.setItem(
			SETTINGS_STORAGE_KEY,
			JSON.stringify(
				getCurrentSettings(),
			),
		)
	} catch {
		// Storage can be unavailable in private
		// or restricted browsing contexts.
	}
}


// Named and shareable presets

function getSavedPresets() {
	try {
		const saved =
			localStorage.getItem(
				PRESETS_STORAGE_KEY,
			)

		if (
			!saved
		) {
			return {}
		}

		const presets =
			JSON.parse(
				saved,
			)

		return presets &&
			typeof presets ===
				'object'
			? presets
			: {}
	} catch {
		return {}
	}
}

function refreshPresetEntries() {
	const localPresets =
		getSavedPresets()

	presetEntries.value = [
		...DEFAULT_PRESETS.map(
			(preset) => ({
				name: preset.name,
				code: preset.code,
				source: 'default',
			}),
		),

		...Object.keys(
			localPresets,
		)
			.sort()
			.map(
				(name) => ({
					name,
					settings:
						localPresets[name],
					source: 'local',
				}),
			),
	]
}

function loadPresetEntry(
	entry,
) {
	try {
		const settings =
			entry.source ===
			'default'
				? decodePreset(
					entry.code,
				)
				: getSavedPresets()[
					entry.name
				]

		openPreset(
			settings,
			entry.name,
		)
	} catch {
		window.alert(
			`Preset “${entry.name}” is invalid.`,
		)
	}
}

function openPreset(
	settings,
	name,
) {
	const completeSettings =
		fillPresetDefaults(
			settings,
		)

	if (
		!completeSettings
	) {
		return false
	}

	const applyOpenedPreset =
		(settingsToApply) => {
			const applied =
				camera &&
				controls
					? applyPreset(
						settingsToApply,
					)
					: applySettings(
						settingsToApply,
					)

			if (
				applied
			) {
				activePresetName.value =
					name
			}
		}

	if (
		completeSettings.pointDensity >
		40
	) {
		requestPresetConfirmation({
			title: 'High point density',
			message:
				`“${name}” uses density ${completeSettings.pointDensity}, which may load slowly or lag without a modern GPU. You can load it at density 20 instead.`,
			confirmLabel: 'Load at 20',
			alternateLabel:
				`Keep ${completeSettings.pointDensity}`,
			onConfirm: () => {
				applyOpenedPreset({
					...completeSettings,
					pointDensity: 20,
				})
			},
			onAlternate: () => {
				applyOpenedPreset(
					completeSettings,
				)
			},
		})

		return true
	}

	applyOpenedPreset(
		completeSettings,
	)

	return true
}

function saveNewPreset() {
	const name =
		newPresetName.value
			.trim()

	if (
		!name
	) {
		return
	}

	const presets =
		getSavedPresets()

	if (
		presets[name]
	) {
		requestPresetConfirmation({
			title: 'Overwrite preset?',
			message:
				`Replace “${name}” with your current settings and camera?`,
			confirmLabel: 'Overwrite',
			onConfirm: () => {
				savePresetWithName(
					name,
				)
			},
		})

		return
	}

	savePresetWithName(
		name,
	)
}

function savePresetWithName(
	name,
) {
	const presets =
		getSavedPresets()

	presets[name] =
		getCurrentSettings()

	storeSavedPresets(
		presets,
	)

	newPresetName.value = ''
	activePresetName.value =
		name
	refreshPresetEntries()
}

function overwritePresetEntry(
	entry,
) {
	if (
		entry.source !==
		'local'
	) {
		return
	}

	requestPresetConfirmation({
		title: 'Overwrite preset?',
		message:
			`Replace “${entry.name}” with your current settings and camera?`,
		confirmLabel: 'Overwrite',
		onConfirm: () => {
			savePresetWithName(
				entry.name,
			)
		},
	})
}

function deletePresetEntry(
	entry,
) {
	if (
		entry.source !==
		'local'
	) {
		return
	}

	requestPresetConfirmation({
		title: 'Delete preset?',
		message:
			`Permanently delete “${entry.name}”?`,
		confirmLabel: 'Delete',
		danger: true,
		onConfirm: () => {
			const presets =
				getSavedPresets()

			delete presets[entry.name]

			storeSavedPresets(
				presets,
			)

			if (
				activePresetName.value ===
				entry.name
			) {
				activePresetName.value =
					'None'
			}

			refreshPresetEntries()
		},
	})
}

function requestPresetConfirmation({
	title,
	message,
	confirmLabel,
	alternateLabel = '',
	danger = false,
	onConfirm,
	onAlternate = null,
}) {
	pendingPresetAction =
		onConfirm
	pendingPresetAlternateAction =
		onAlternate

	presetConfirmation.value = {
		open: true,
		title,
		message,
		confirmLabel,
		alternateLabel,
		danger,
	}
}

function closePresetConfirmation() {
	presetConfirmation.value.open =
		false
	pendingPresetAction = null
	pendingPresetAlternateAction = null
}

function confirmPresetAction() {
	const action =
		pendingPresetAction

	closePresetConfirmation()
	action?.()
}

function confirmPresetAlternateAction() {
	const action =
		pendingPresetAlternateAction

	closePresetConfirmation()
	action?.()
}

function storeSavedPresets(
	presets,
) {
	try {
		localStorage.setItem(
			PRESETS_STORAGE_KEY,
			JSON.stringify(
				presets,
			),
		)

		return true
	} catch {
		return false
	}
}

function applyPreset(
	settings,
) {
	const completeSettings =
		fillPresetDefaults(
			settings,
		)

	if (
		!applySettings(
			completeSettings,
		)
	) {
		return false
	}

	updateShapeBindingVisibility()

	updatePaletteBindingVisibility()

	pane
		?.refresh()

	if (
		dots
	) {
		updateRenderMode()
		updateGeometry()
	}

	if (
		camera &&
		controls
	) {
		rebuildCamera()
	}

	saveSettings()

	return true
}

function encodePreset(
	settings,
) {
	return btoa(
		JSON.stringify({
			version: 1,
			settings,
		}),
	)
		.replaceAll(
			'+',
			'-',
		)
		.replaceAll(
			'/',
			'_',
		)
		.replace(
			/=+$/,
			'',
		)
}

function decodePreset(
	input,
) {
	let code =
		input.trim()

	try {
		const url =
			new URL(
				code,
				window.location.href,
			)

		code =
			url.searchParams.get(
				'preset',
			) ||
			code
	} catch {
		// The input may be a preset code,
		// rather than a URL.
	}

	code =
		code.replace(
			/^color-explorer:/,
			'',
		)
			.replaceAll(
				'-',
				'+',
			)
			.replaceAll(
				'_',
				'/',
			)

	while (
		code.length % 4 !== 0
	) {
		code += '='
	}

	const payload =
		JSON.parse(
			atob(
				code,
			),
		)

	return payload.settings ||
		payload
}

function getShareUrl() {
	const url =
		new URL(
			window.location.href,
		)

	url.searchParams.set(
		'preset',
		encodePreset(
			getCurrentSettings(),
		),
	)

	return url.toString()
}

async function copyShareUrl() {
	const url =
		getShareUrl()

	try {
		await navigator.clipboard.writeText(
			url,
		)

		window.alert(
			'Share URL copied.',
		)
	} catch {
		window.prompt(
			'Copy this share URL:',
			url,
		)
	}
}

async function copyPresetCode() {
	const code =
		`color-explorer:${encodePreset(
			getCurrentSettings(),
		)}`

	try {
		await navigator.clipboard.writeText(
			code,
		)

		window.alert(
			'Preset code copied.',
		)
	} catch {
		window.prompt(
			'Copy this preset code:',
			code,
		)
	}
}

function importPreset() {
	const input =
		window.prompt(
			'Paste a Color Explorer share URL or preset code:',
		)

	if (
		!input
	) {
		return
	}

	try {
		openPreset(
			decodePreset(
				input,
			),
			'Imported preset',
		)
	} catch {
		window.alert(
			'That preset URL or code is invalid.',
		)
	}
}

function loadPresetFromUrl() {
	const code =
		new URLSearchParams(
			window.location.search,
		)
			.get(
				'preset',
			)

	if (
		!code
	) {
		return
	}

	try {
		openPreset(
			decodePreset(
				code,
			),
			'Shared preset',
		)
	} catch {
		// Ignore malformed shared URLs and
		// retain the locally saved settings.
	}
}


// Color axes

const hsvAxes = {
	h: '+z',
	s: '+x',
	v: '+y',
}

const hslAxes = {
	h: '+z',
	s: '+x',
	l: '+y',
}


// Normalized coordinates

function getLinearAlpha(index) {
	return index /
		(
			point_density.value -
			1
		)
}

function getCircularAlpha(index) {
	return index /
		point_density.value
}


// Shape positions from normalized coordinates

function getCubePositionFromCoords(
	xAlpha,
	yAlpha,
	zAlpha,
) {
	const x =
		(
			xAlpha -
			0.5
		) *
		cube_width.value

	const y =
		(
			yAlpha -
			0.5
		) *
		cube_height.value

	const z =
		(
			zAlpha -
			0.5
		) *
		cube_depth.value

	return {
		x,
		y,
		z,
	}
}

function getCylinderPositionFromCoords(
	radiusAlpha,
	heightAlpha,
	angleAlpha,
) {
	const radius =
		radiusAlpha *
		cylinder_radius.value +
		cylinder_gap.value

	const angle =
		angleAlpha *
		Math.PI *
		2

	const y =
		(
			heightAlpha -
			0.5
		) *
		cylinder_height.value

	const x =
		Math.cos(angle) *
		radius

	const z =
		Math.sin(angle) *
		radius

	return {
		x,
		y,
		z,
	}
}

function getTorusPositionFromCoords(
	tubeDepth,
	tubeAngleAlpha,
	torusAngleAlpha,
) {
	const tubeAngle =
		-tubeAngleAlpha *
			Math.PI *
			2 +
		THREE.MathUtils.degToRad(
			torus_rotation.value,
		)

	const torusAngle =
		torusAngleAlpha *
		Math.PI *
		2

	const tubeRadius =
		tubeDepth *
		TORUS_TUBE_RADIUS

	const ringDistance =
		TORUS_MAJOR_RADIUS +
		Math.cos(
			tubeAngle,
		) *
		tubeRadius

	const x =
		Math.cos(
			torusAngle,
		) *
		ringDistance

	const y =
		Math.sin(
			tubeAngle,
		) *
		tubeRadius

	const z =
		Math.sin(
			torusAngle,
		) *
		ringDistance

	return {
		x,
		y,
		z,
	}
}

function getPositionFromCoords(
	coords,
) {
	switch (shape.value) {
		case 'cube':
			return getCubePositionFromCoords(
				coords.x,
				coords.y,
				coords.z,
			)

		case 'cylinder':
			return getCylinderPositionFromCoords(
				coords.x,
				coords.y,
				coords.z,
			)

		case 'torus':
			return getTorusPositionFromCoords(
				coords.x,
				coords.y,
				coords.z,
			)
	}
}


// Shape positions from point indexes

function getDotPositionCube(
	i,
	j,
	k,
) {
	return getCubePositionFromCoords(
		getLinearAlpha(i),
		getLinearAlpha(j),
		getLinearAlpha(k),
	)
}

function getDotPositionCylinder(
	i,
	j,
	k,
) {
	return getCylinderPositionFromCoords(
		getLinearAlpha(i),
		getLinearAlpha(j),
		getCircularAlpha(k),
	)
}

function getDotPositionTorus(
	i,
	j,
	k,
) {
	return getTorusPositionFromCoords(
		getLinearAlpha(i),
		getCircularAlpha(j),
		getCircularAlpha(k),
	)
}

function getDotPosition(
	i,
	j,
	k,
) {
	switch (shape.value) {
		case 'cube':
			return getDotPositionCube(
				i,
				j,
				k,
			)

		case 'cylinder':
			return getDotPositionCylinder(
				i,
				j,
				k,
			)

		case 'torus':
			return getDotPositionTorus(
				i,
				j,
				k,
			)
	}
}


// Color space

function getDotColorHSL(
	x,
	y,
	z,
) {
	const coords = {
		x: getLinearAlpha(x),
		y: getLinearAlpha(y),
		z: getLinearAlpha(z),
	}

	const h =
		getAxisValue(
			coords,
			hslAxes.h,
		)

	const s =
		getAxisValue(
			coords,
			hslAxes.s,
		)

	const l =
		getAxisValue(
			coords,
			hslAxes.l,
		)

	return new THREE.Color()
		.setHSL(
			h,
			s,
			l,
			THREE.SRGBColorSpace,
		)
}

function getDotColorHSV(
	x,
	y,
	z,
) {
	const coords = {
		x: getLinearAlpha(x),
		y: getLinearAlpha(y),
		z: getLinearAlpha(z),
	}

	const h =
		getAxisValue(
			coords,
			hsvAxes.h,
		)

	const s =
		getAxisValue(
			coords,
			hsvAxes.s,
		)

	const v =
		getAxisValue(
			coords,
			hsvAxes.v,
		)

	return hsvToColor(
		h,
		s,
		v,
	)
}

function getAxisValue(
	coords,
	axis,
) {
	const direction =
		axis[0]

	const axisName =
		axis[1]

	const value =
		coords[
			axisName
		]

	if (
		direction === '-'
	) {
		return 1 - value
	}

	return value
}

function hsvToColor(
	h,
	s,
	v,
) {
	h = h % 1

	const sector =
		Math.floor(
			h * 6,
		)

	const fraction =
		h * 6 -
		sector

	const p =
		v *
		(
			1 - s
		)

	const q =
		v *
		(
			1 -
			fraction *
			s
		)

	const t =
		v *
		(
			1 -
			(
				1 -
				fraction
			) *
			s
		)

	let r
	let g
	let b

	switch (
		sector % 6
	) {
		case 0:
			r = v
			g = t
			b = p
			break

		case 1:
			r = q
			g = v
			b = p
			break

		case 2:
			r = p
			g = v
			b = t
			break

		case 3:
			r = p
			g = q
			b = v
			break

		case 4:
			r = t
			g = p
			b = v
			break

		case 5:
			r = v
			g = p
			b = q
			break
	}

	return new THREE.Color()
		.setRGB(
			r,
			g,
			b,
			THREE.SRGBColorSpace,
		)
}


// Palette color conversion

function hexToRgb(hex) {
	let value =
		hex.replace(
			'#',
			'',
		)

	if (
		value.length === 3
	) {
		value =
			value
				.split('')
				.map(
					(character) =>
						character +
						character
				)
				.join('')
	}

	value =
		value.slice(
			0,
			6,
		)

	const number =
		Number.parseInt(
			value,
			16,
		)

	return {
		r:
			(
				(
					number >>
					16
				) &
				255
			) /
			255,

		g:
			(
				(
					number >>
					8
				) &
				255
			) /
			255,

		b:
			(
				number &
				255
			) /
			255,
	}
}

function rgbToHsv(
	r,
	g,
	b,
) {
	const max =
		Math.max(
			r,
			g,
			b,
		)

	const min =
		Math.min(
			r,
			g,
			b,
		)

	const delta =
		max -
		min

	let h = 0

	if (
		delta !== 0
	) {
		if (
			max === r
		) {
			h =
				(
					(
						g - b
					) /
					delta
				) % 6
		} else if (
			max === g
		) {
			h =
				(
					b - r
				) /
				delta +
				2
		} else {
			h =
				(
					r - g
				) /
				delta +
				4
		}

		h /= 6

		if (
			h < 0
		) {
			h += 1
		}
	}

	const s =
		max === 0
			? 0
			: delta / max

	const v =
		max

	return {
		h,
		s,
		v,
	}
}

function hexToHsv(hex) {
	const {
		r,
		g,
		b,
	} =
		hexToRgb(
			hex,
		)

	return rgbToHsv(
		r,
		g,
		b,
	)
}

function setAxisCoord(
	coords,
	axis,
	value,
) {
	const direction =
		axis[0]

	const axisName =
		axis[1]

	coords[
		axisName
	] =
		direction === '-'
			? 1 - value
			: value
}

function hsvToCoords(
	h,
	s,
	v,
) {
	const coords = {
		x: 0,
		y: 0,
		z: 0,
	}

	setAxisCoord(
		coords,
		hsvAxes.h,
		h,
	)

	setAxisCoord(
		coords,
		hsvAxes.s,
		s,
	)

	setAxisCoord(
		coords,
		hsvAxes.v,
		v,
	)

	return coords
}

function getPaletteColorPosition(
	hex,
) {
	const {
		h,
		s,
		v,
	} =
		hexToHsv(
			hex,
		)

	const coords =
		hsvToCoords(
			h,
			s,
			v,
		)

	const position =
		getPositionFromCoords(
			coords,
		)

	return new THREE.Vector3(
		position.x,
		position.y,
		position.z,
	)
}

function getActivePaletteColors() {
	const colors = []

	for (
		let i = 0;
		i < palette_size.value;
		i++
	) {
		colors.push(
			palette_colors[
				`color${i + 1}`
			],
		)
	}

	return colors
}


// Palette path ordering

function orderPalettePoints(
	points,
) {
	if (
		points.length <= 2
	) {
		return points.slice()
	}

	let closestA = 0
	let closestB = 1

	let closestDistance =
		Infinity

	for (
		let i = 0;
		i < points.length;
		i++
	) {
		for (
			let j = i + 1;
			j < points.length;
			j++
		) {
			const distance =
				points[
					i
				].position
					.distanceToSquared(
						points[
							j
						].position,
					)

			if (
				distance <
				closestDistance
			) {
				closestDistance =
					distance

				closestA = i
				closestB = j
			}
		}
	}

	const ordered = [
		points[
			closestA
		],
		points[
			closestB
		],
	]

	const remaining =
		points.filter(
			(_, index) =>
				index !==
					closestA &&
				index !==
					closestB
		)

	while (
		remaining.length > 0
	) {
		let bestIndex = 0
		let bestDistance =
			Infinity

		let addToStart =
			false

		for (
			let i = 0;
			i < remaining.length;
			i++
		) {
			const distanceToStart =
				remaining[
					i
				].position
					.distanceToSquared(
						ordered[
							0
						].position,
					)

			if (
				distanceToStart <
				bestDistance
			) {
				bestDistance =
					distanceToStart

				bestIndex = i
				addToStart = true
			}

			const distanceToEnd =
				remaining[
					i
				].position
					.distanceToSquared(
						ordered[
							ordered.length -
							1
						].position,
					)

			if (
				distanceToEnd <
				bestDistance
			) {
				bestDistance =
					distanceToEnd

				bestIndex = i
				addToStart = false
			}
		}

		const point =
			remaining.splice(
				bestIndex,
				1,
			)[0]

		if (
			addToStart
		) {
			ordered.unshift(
				point,
			)
		} else {
			ordered.push(
				point,
			)
		}
	}

	return ordered
}

function rebuildPaletteData() {
	const colors =
		getActivePaletteColors()

	const points =
		colors.map(
			(hex) => ({
				hex,

				position:
					getPaletteColorPosition(
						hex,
					),
			}),
		)

	palettePoints =
		orderPalettePoints(
			points,
		)

	const controlPoints =
		palettePoints.map(
			(point) =>
				point.position,
		)

	paletteCurve =
		controlPoints.length >= 2
			? new THREE.CatmullRomCurve3(
				controlPoints,
				false,
				'centripetal',
			)
			: null

	palettePath =
		paletteCurve
			? paletteCurve.getPoints(
				(
					controlPoints.length -
					1
				) *
					PALETTE_CURVE_SEGMENTS,
			)
			: controlPoints

	paletteSegments = []

	for (
		let i = 0;
		i <
			palettePath.length -
				1;
		i++
	) {
		const start =
			palettePath[
				i
			]

		const end =
			palettePath[
				i + 1
			]

		const abx =
			end.x -
			start.x

		const aby =
			end.y -
			start.y

		const abz =
			end.z -
			start.z

		const lengthSquared =
			abx * abx +
			aby * aby +
			abz * abz

		if (
			lengthSquared <
			0.0000001
		) {
			continue
		}

		paletteSegments.push({
			ax: start.x,
			ay: start.y,
			az: start.z,

			bx: end.x,
			by: end.y,
			bz: end.z,

			abx,
			aby,
			abz,

			lengthSquared,

			length:
				Math.sqrt(
					lengthSquared,
				),

			minX:
				Math.min(
					start.x,
					end.x,
				),

			maxX:
				Math.max(
					start.x,
					end.x,
				),

			minY:
				Math.min(
					start.y,
					end.y,
				),

			maxY:
				Math.max(
					start.y,
					end.y,
				),

			minZ:
				Math.min(
					start.z,
					end.z,
				),

			maxZ:
				Math.max(
					start.z,
					end.z,
				),
		})
	}
}


// Tunnel deformation

function setLatticeNeighbor(
	neighborIndexes,
	restLengths,
	positions,
	pointIndex,
	neighborSlot,
	neighborIndex,
) {
	const neighborOffset =
		pointIndex *
		6 +
		neighborSlot

	neighborIndexes[
		neighborOffset
	] =
		neighborIndex

	const pointOffset =
		pointIndex *
		3

	const adjacentOffset =
		neighborIndex *
		3

	const dx =
		positions[
			adjacentOffset
		] -
		positions[
			pointOffset
		]

	const dy =
		positions[
			adjacentOffset + 1
		] -
		positions[
			pointOffset + 1
		]

	const dz =
		positions[
			adjacentOffset + 2
		] -
		positions[
			pointOffset + 2
		]

	restLengths[
		neighborOffset
	] =
		Math.sqrt(
			dx * dx +
			dy * dy +
			dz * dz,
		)
}

function createLatticeNeighbors(
	positions,
	density,
) {
	const pointCount =
		density *
		density *
		density

	const neighborIndexes =
		new Int32Array(
			pointCount * 6,
		)

	neighborIndexes.fill(
		-1,
	)

	const restLengths =
		new Float32Array(
			pointCount * 6,
		)

	const iStride =
		density *
		density

	const jStride =
		density

	const wrapJ =
		shape.value ===
		'torus'

	const wrapK =
		shape.value ===
		'cylinder' ||
		shape.value ===
		'torus'

	for (
		let i = 0;
		i < density;
		i++
	) {
		for (
			let j = 0;
			j < density;
			j++
		) {
			for (
				let k = 0;
				k < density;
				k++
			) {
				const pointIndex =
					i *
						iStride +
					j *
						jStride +
					k

				let neighborSlot = 0

				if (
					i > 0
				) {
					setLatticeNeighbor(
						neighborIndexes,
						restLengths,
						positions,
						pointIndex,
						neighborSlot++,
						pointIndex -
							iStride,
					)
				}

				if (
					i < density - 1
				) {
					setLatticeNeighbor(
						neighborIndexes,
						restLengths,
						positions,
						pointIndex,
						neighborSlot++,
						pointIndex +
							iStride,
					)
				}

				if (
					j > 0
				) {
					setLatticeNeighbor(
						neighborIndexes,
						restLengths,
						positions,
						pointIndex,
						neighborSlot++,
						pointIndex -
							jStride,
					)
				} else if (
					wrapJ
				) {
					setLatticeNeighbor(
						neighborIndexes,
						restLengths,
						positions,
						pointIndex,
						neighborSlot++,
						pointIndex +
							(
								density - 1
							) *
							jStride,
					)
				}

				if (
					j < density - 1
				) {
					setLatticeNeighbor(
						neighborIndexes,
						restLengths,
						positions,
						pointIndex,
						neighborSlot++,
						pointIndex +
							jStride,
					)
				} else if (
					wrapJ
				) {
					setLatticeNeighbor(
						neighborIndexes,
						restLengths,
						positions,
						pointIndex,
						neighborSlot++,
						pointIndex -
							(
								density - 1
							) *
							jStride,
					)
				}

				if (
					k > 0
				) {
					setLatticeNeighbor(
						neighborIndexes,
						restLengths,
						positions,
						pointIndex,
						neighborSlot++,
						pointIndex - 1,
					)
				} else if (
					wrapK
				) {
					setLatticeNeighbor(
						neighborIndexes,
						restLengths,
						positions,
						pointIndex,
						neighborSlot++,
						pointIndex +
							density - 1,
					)
				}

				if (
					k < density - 1
				) {
					setLatticeNeighbor(
						neighborIndexes,
						restLengths,
						positions,
						pointIndex,
						neighborSlot,
						pointIndex + 1,
					)
				} else if (
					wrapK
				) {
					setLatticeNeighbor(
						neighborIndexes,
						restLengths,
						positions,
						pointIndex,
						neighborSlot,
						pointIndex -
							density + 1,
					)
				}
			}
		}
	}

	return {
		neighborIndexes,
		restLengths,
	}
}

function relaxPaletteLattice(
	original,
	density,
) {
	let current =
		new Float32Array(
			original,
		)

	if (
		!tunnel_enabled.value ||
		tunnel_radius.value <= 0 ||
		paletteSegments.length === 0
	) {
		return current
	}

	const pointCount =
		original.length /
		3

	let next =
		new Float32Array(
			original.length,
		)

	const {
		neighborIndexes,
		restLengths,
	} =
		createLatticeNeighbors(
			original,
			density,
		)

	const influenceRadius =
		tunnel_radius.value *
		tunnel_influence_scale.value

	const influenceRadiusSquared =
		influenceRadius *
		influenceRadius

	let paletteCenterX = 0
	let paletteCenterY = 0
	let paletteCenterZ = 0

	for (
		const point of
		palettePath
	) {
		paletteCenterX +=
			point.x

		paletteCenterY +=
			point.y

		paletteCenterZ +=
			point.z
	}

	paletteCenterX /=
		palettePath.length

	paletteCenterY /=
		palettePath.length

	paletteCenterZ /=
		palettePath.length

	for (
		let step = 0;
		step <
			lattice_relaxation_steps.value;
		step++
	) {
		for (
			let pointIndex = 0;
			pointIndex < pointCount;
			pointIndex++
		) {
			const pointOffset =
				pointIndex *
				3

			const px =
				current[
					pointOffset
				]

			const py =
				current[
					pointOffset + 1
				]

			const pz =
				current[
					pointOffset + 2
				]

			let repulsionX = 0
			let repulsionY = 0
			let repulsionZ = 0
			let repulsionWeight = 0

			for (
				let segmentIndex = 0;
				segmentIndex <
					paletteSegments.length;
				segmentIndex++
			) {
				const segment =
					paletteSegments[
						segmentIndex
					]

				if (
					px <
						segment.minX -
							influenceRadius ||
					px >
						segment.maxX +
							influenceRadius ||
					py <
						segment.minY -
							influenceRadius ||
					py >
						segment.maxY +
							influenceRadius ||
					pz <
						segment.minZ -
							influenceRadius ||
					pz >
						segment.maxZ +
							influenceRadius
				) {
					continue
				}

				const apx =
					px -
					segment.ax

				const apy =
					py -
					segment.ay

				const apz =
					pz -
					segment.az

				let segmentAlpha =
					(
						apx *
							segment.abx +
						apy *
							segment.aby +
						apz *
							segment.abz
					) /
					segment.lengthSquared

				segmentAlpha =
					Math.max(
						0,
						Math.min(
							1,
							segmentAlpha,
						),
					)

				let dx =
					px -
					(
						segment.ax +
						segment.abx *
							segmentAlpha
					)

				let dy =
					py -
					(
						segment.ay +
						segment.aby *
							segmentAlpha
					)

				let dz =
					pz -
					(
						segment.az +
						segment.abz *
							segmentAlpha
					)

				const distanceSquared =
					dx * dx +
					dy * dy +
					dz * dz

				if (
					distanceSquared >=
						influenceRadiusSquared
				) {
					continue
				}

				const distance =
					Math.sqrt(
						distanceSquared,
					)

				if (
					distance > 0.000001
				) {
					dx /= distance
					dy /= distance
					dz /= distance
				} else if (
					Math.abs(
						segment.abx /
							segment.length,
					) < 0.9
				) {
					dx = 0
					dy = segment.abz
					dz = -segment.aby
				} else {
					dx = -segment.abz
					dy = 0
					dz = segment.abx
				}

				if (
					distance <= 0.000001
				) {
					const directionLength =
						Math.sqrt(
							dx * dx +
							dy * dy +
							dz * dz,
						)

					dx /= directionLength
					dy /= directionLength
					dz /= directionLength

					if (
						dx *
							(
								px -
								paletteCenterX
							) +
						dy *
							(
								py -
								paletteCenterY
							) +
						dz *
							(
								pz -
								paletteCenterZ
							) <
						0
					) {
						dx = -dx
						dy = -dy
						dz = -dz
					}
				}

				const influenceAlpha =
					1 -
					distance /
						influenceRadius

				const smoothWeight =
					influenceAlpha *
					influenceAlpha *
					(
						3 -
						2 *
							influenceAlpha
					) *
					segment.length

				repulsionX +=
					dx *
					smoothWeight

				repulsionY +=
					dy *
					smoothWeight

				repulsionZ +=
					dz *
					smoothWeight

				repulsionWeight +=
					smoothWeight
			}

			if (
				repulsionWeight > 0.000001
			) {
				const fieldStrength =
					repulsionWeight /
					(
						repulsionWeight +
						influenceRadius *
							0.5
					)

				const repulsionScale =
					tunnel_radius.value *
					lattice_repulsion_strength.value *
					fieldStrength /
					repulsionWeight

				repulsionX *=
					repulsionScale

				repulsionY *=
					repulsionScale

				repulsionZ *=
					repulsionScale
			}

			let springX = 0
			let springY = 0
			let springZ = 0
			let neighborCount = 0

			const neighborOffset =
				pointIndex *
				6

			for (
				let neighborSlot = 0;
				neighborSlot < 6;
				neighborSlot++
			) {
				const adjacentIndex =
					neighborIndexes[
						neighborOffset +
						neighborSlot
					]

				if (
					adjacentIndex < 0
				) {
					break
				}

				const adjacentOffset =
					adjacentIndex *
					3

				const dx =
					current[
						adjacentOffset
					] -
					px

				const dy =
					current[
						adjacentOffset + 1
					] -
					py

				const dz =
					current[
						adjacentOffset + 2
					] -
					pz

				const currentLength =
					Math.sqrt(
						dx * dx +
						dy * dy +
						dz * dz,
					)

				if (
					currentLength > 0.000001
				) {
					const springScale =
						(
							currentLength -
							restLengths[
								neighborOffset +
								neighborSlot
							]
						) /
						currentLength

					springX +=
						dx *
						springScale

					springY +=
						dy *
						springScale

					springZ +=
						dz *
						springScale
				}

				neighborCount++
			}

			const springScale =
				lattice_spring_strength.value /
				neighborCount

			next[
				pointOffset
			] =
				px +
				repulsionX +
				springX *
					springScale +
				(
					original[
						pointOffset
					] -
					px
				) *
					lattice_restore_strength.value

			next[
				pointOffset + 1
			] =
				py +
				repulsionY +
				springY *
					springScale +
				(
					original[
						pointOffset + 1
					] -
					py
				) *
					lattice_restore_strength.value

			next[
				pointOffset + 2
			] =
				pz +
				repulsionZ +
				springZ *
					springScale +
				(
					original[
						pointOffset + 2
					] -
					pz
				) *
					lattice_restore_strength.value
		}

		const swap =
			current

		current = next
		next = swap
	}

	return current
}


// Camera

function resetCamera() {
	const defaults =
		getDefaultPresetSettings()

	camera_projection.value =
		defaults.cameraProjection
	camera_fov.value =
		defaults.cameraFov
	camera_ortho_size.value =
		defaults.cameraOrthoSize
	camera_near.value =
		defaults.cameraNear
	camera_far.value =
		defaults.cameraFar

	camera.position.set(
		defaults.camera.position.x,
		defaults.camera.position.y,
		defaults.camera.position.z,
	)

	controls.target.set(
		defaults.camera.target.x,
		defaults.camera.target.y,
		defaults.camera.target.z,
	)

	camera.zoom =
		defaults.camera.zoom
	camera.updateProjectionMatrix()

	controls.update()

	localStorage.removeItem(
		CAMERA_STORAGE_KEY,
	)

	rebuildCamera()
}

function createCamera() {
	const aspect =
		window.innerWidth /
		window.innerHeight

	const near =
		camera_near.value

	const far =
		Math.max(
			camera_far.value,
			near + 0.001,
		)

	if (
		camera_projection.value ===
		'orthographic'
	) {
		const halfHeight =
			camera_ortho_size.value *
			0.5

		const halfWidth =
			halfHeight *
			aspect

		return new THREE.OrthographicCamera(
			-halfWidth,
			halfWidth,
			halfHeight,
			-halfHeight,
			near,
			far,
		)
	}

	return new THREE.PerspectiveCamera(
		camera_fov.value,
		aspect,
		near,
		far,
	)
}

function isValidCameraState(
	state,
) {
	return Boolean(
		state &&
		state.position &&
		state.target &&
		[
			state.position.x,
			state.position.y,
			state.position.z,
			state.target.x,
			state.target.y,
			state.target.z,
		].every(
			Number.isFinite,
		),
	)
}

function getCurrentCameraState() {
	if (
		!camera ||
		!controls
	) {
		return null
	}

	return {
		position: {
			x: camera.position.x,
			y: camera.position.y,
			z: camera.position.z,
		},

		target: {
			x: controls.target.x,
			y: controls.target.y,
			z: controls.target.z,
		},

		zoom:
			camera.zoom,
	}
}

function applyCameraState(
	state,
) {
	if (
		!isValidCameraState(
			state,
		) ||
		!camera ||
		!controls
	) {
		return
	}

	camera.position.set(
		state.position.x,
		state.position.y,
		state.position.z,
	)

	controls.target.set(
		state.target.x,
		state.target.y,
		state.target.z,
	)

	if (
		Number.isFinite(
			state.zoom,
		)
	) {
		camera.zoom =
			state.zoom
		camera.updateProjectionMatrix()
	}

	controls.update()
}

function setupCamera(
	stateOverride = null,
) {
	camera =
		createCamera()

	const state =
		stateOverride ||
		pendingCameraState ||
		loadCameraState()

	if (
		state
	) {
		camera.position.set(
			state.position.x,
			state.position.y,
			state.position.z,
		)

		if (
			Number.isFinite(
				state.zoom,
			)
		) {
			camera.zoom =
				state.zoom
			camera.updateProjectionMatrix()
		}
	} else {
		camera.position.set(
			0,
			0,
			8,
		)
	}
}

function rebuildCamera() {
	const state =
		getCurrentCameraState()

	controls
		?.removeEventListener(
			'change',
			handleCameraChange,
		)

	controls
		?.dispose()

	setupCamera(
		state,
	)

	setupControls(
		state,
	)

	if (
		renderMode.value ===
			'squares' &&
		material
	) {
		material.size =
			getSquarePointSize()
	}

	updateCameraBindingVisibility()

	utilityPane
		?.refresh()

	sortNeeded = true
	saveSettings()
}

function loadCameraState() {
	const saved =
		localStorage.getItem(
			CAMERA_STORAGE_KEY,
		)

	if (
		!saved
	) {
		return null
	}

	try {
		const state =
			JSON.parse(
				saved,
			)

		if (
			!isValidCameraState(
				state,
			)
		) {
			throw new Error(
				'Invalid camera state',
			)
		}

		return state
	} catch {
		localStorage.removeItem(
			CAMERA_STORAGE_KEY,
		)

		return null
	}
}

function saveCameraState() {
	const state =
		getCurrentCameraState()

	if (
		!state
	) {
		return
	}

	localStorage.setItem(
		CAMERA_STORAGE_KEY,
		JSON.stringify(
			state,
		),
	)
}


// Point materials

function getSquarePointSize() {
	if (
		!camera
			?.isOrthographicCamera ||
		!renderer
	) {
		return dot_size.value
	}

	const visibleHeight =
		(
			camera.top -
			camera.bottom
		) /
		camera.zoom

	return dot_size.value *
		renderer.domElement.clientHeight /
		visibleHeight
}

function updateDotSize() {
	if (
		material
	) {
		if (
			renderMode.value ===
				'splats'
		) {
			material
				.uniforms
				.dotSize
				.value =
					dot_size.value
		} else {
			material.size =
				getSquarePointSize()
		}
	}

	saveSettings()
}

function createPointMaterial() {
	if (
		renderMode.value ===
		'splats'
	) {
		return createSplatMaterial()
	}

	return createSquareMaterial()
}

function createSquareMaterial() {
	return new THREE.PointsMaterial({
		size:
			getSquarePointSize(),

		vertexColors:
			true,

		depthTest:
			true,

		depthWrite:
			true,

		transparent:
			false,
	})
}

function createSplatMaterial() {
	return new THREE.ShaderMaterial({
		uniforms: {
			dotSize: {
				value:
					dot_size.value,
			},
		},

		vertexShader: `
			varying vec3 vColor;

			uniform float dotSize;

			void main() {
				vColor = color;

				vec4 mvPosition =
					modelViewMatrix *
					vec4(position, 1.0);

				gl_Position =
					projectionMatrix *
					mvPosition;

				gl_PointSize =
					dotSize *
						600.0 /
						-mvPosition.z;
			}
		`,

		fragmentShader: `
			varying vec3 vColor;

			void main() {
				vec2 centered =
					gl_PointCoord -
					vec2(0.5);

				float radiusSquared =
					dot(
						centered,
						centered
					);

				float alpha =
					exp(
						-radiusSquared * 20.0
					);

				if (alpha < 0.01) {
					discard;
				}

				gl_FragColor =
					vec4(
						vColor,
						alpha
					);
			}
		`,

		vertexColors:
			true,

		transparent:
			true,

		depthWrite:
			false,

		blending:
			THREE.NormalBlending,
	})
}

function updateRenderMode() {
	if (
		!dots
	) {
		return
	}

	material.dispose()

	material =
		createPointMaterial()

	dots.material =
		material

	if (
		renderMode.value ===
		'splats'
	) {
		sortNeeded = true
	}

	saveSettings()
}


// Splat sorting

function sortSplats() {
	camera.updateMatrixWorld()
	dots.updateMatrixWorld()

	const modelViewMatrix =
		new THREE.Matrix4()
			.multiplyMatrices(
				camera.matrixWorldInverse,
				dots.matrixWorld,
			)

	const e =
		modelViewMatrix.elements

	const pointCount =
		basePositions.length /
		3

	for (
		let i = 0;
		i < pointCount;
		i++
	) {
		const offset =
			i *
			3

		const x =
			basePositions[
				offset
			]

		const y =
			basePositions[
				offset + 1
			]

		const z =
			basePositions[
				offset + 2
			]

		depths[
			i
		] =
			e[2] * x +
			e[6] * y +
			e[10] * z +
			e[14]
	}

	sortOrder.sort(
		(a, b) =>
			depths[a] -
			depths[b]
	)

	for (
		let i = 0;
		i < pointCount;
		i++
	) {
		const source =
			sortOrder[
				i
			] *
			3

		const destination =
			i *
			3

		sortedPositions[
			destination
		] =
			basePositions[
				source
			]

		sortedPositions[
			destination + 1
		] =
			basePositions[
				source + 1
			]

		sortedPositions[
			destination + 2
		] =
			basePositions[
				source + 2
			]

		sortedColors[
			destination
		] =
			baseColors[
				source
			]

		sortedColors[
			destination + 1
		] =
			baseColors[
				source + 1
			]

		sortedColors[
			destination + 2
		] =
			baseColors[
				source + 2
			]
	}

	geometry
		.attributes
		.position
		.needsUpdate =
			true

	geometry
		.attributes
		.color
		.needsUpdate =
			true
}


// Scene

function setupScene() {
	scene =
		new THREE.Scene()
}

function setupRenderer() {
	renderer =
		new THREE.WebGLRenderer({
			antialias:
				true,
		})

	renderer.setSize(
		window.innerWidth,
		window.innerHeight,
	)

	threeContainer
		.value
		.appendChild(
			renderer.domElement,
		)
}


// Cloud geometry

function setupGeometry() {
	const density =
		point_density.value

	const pointCount =
		density *
		density *
		density

	pointCountDisplay.value =
		pointCount.toLocaleString()

	const original =
		new Float32Array(
			pointCount * 3,
		)

	const colors =
		new Float32Array(
			pointCount * 3,
		)

	for (
		let i = 0;
		i < density;
		i++
	) {
		for (
			let j = 0;
			j < density;
			j++
		) {
			for (
				let k = 0;
				k < density;
				k++
			) {
				const pointIndex =
					i *
						density *
						density +
					j *
						density +
					k

				const offset =
					pointIndex *
					3

				const position =
					getDotPosition(
						i,
						j,
						k,
					)

				original[
					offset
				] =
					position.x

				original[
					offset + 1
				] =
					position.y

				original[
					offset + 2
				] =
					position.z

				const color =
					getDotColorHSV(
						i,
						j,
						k,
					)

				colors[
					offset
				] =
					color.r

				colors[
					offset + 1
				] =
					color.g

				colors[
					offset + 2
				] =
					color.b
			}
		}
	}

	originalPositions =
		original

	const positions =
		relaxPaletteLattice(
			originalPositions,
			density,
		)

	setupGeometryBuffers(
		positions,
		colors,
	)
}

function setupGeometryBuffers(
	positions,
	colors,
) {
	geometry =
		new THREE.BufferGeometry()

	basePositions =
		positions

	baseColors =
		colors

	const pointCount =
		basePositions.length /
		3

	sortOrder =
		Array.from(
			{
				length:
					pointCount,
			},
			(_, i) => i,
		)

	depths =
		new Float32Array(
			pointCount,
		)

	sortedPositions =
		new Float32Array(
			basePositions,
		)

	sortedColors =
		new Float32Array(
			baseColors,
		)

	geometry.setAttribute(
		'position',
		new THREE.BufferAttribute(
			sortedPositions,
			3,
		),
	)

	geometry.setAttribute(
		'color',
		new THREE.BufferAttribute(
			sortedColors,
			3,
		),
	)
}

function updateGeometry() {
	if (
		!dots
	) {
		return
	}

	rebuildPaletteData()
	rebuildPaletteOverlay()

	const oldGeometry =
		geometry

	setupGeometry()

	dots.geometry =
		geometry

	oldGeometry
		?.dispose()

	if (
		renderMode.value ===
		'splats'
	) {
		sortNeeded = true
	}

	saveSettings()
}

function setupPoints() {
	material =
		createPointMaterial()

	dots =
		new THREE.Points(
			geometry,
			material,
		)

	scene.add(
		dots,
	)
}


// Palette overlay

function setupPalette() {
	rebuildPaletteData()
	rebuildPaletteOverlay()
}

function disposeMaterial(
	materialToDispose,
) {
	if (
		Array.isArray(
			materialToDispose,
		)
	) {
		for (
			const item of
				materialToDispose
		) {
			item.dispose()
		}

		return
	}

	materialToDispose
		?.dispose()
}

function disposePaletteGroup() {
	if (
		!paletteGroup
	) {
		return
	}

	scene.remove(
		paletteGroup,
	)

	paletteGroup.traverse(
		(object) => {
			object.geometry
				?.dispose()

			disposeMaterial(
				object.material,
			)
		},
	)

	paletteGroup = null
}

function createPaletteCurve() {
	if (
		!paletteCurve
	) {
		return null
	}

	const lineGeometry =
		new THREE.TubeGeometry(
			paletteCurve,
			Math.max(
				PALETTE_CURVE_SEGMENTS,
				(
					palettePoints.length -
					1
				) *
					PALETTE_CURVE_SEGMENTS,
			),
			PALETTE_LINE_RADIUS,
			8,
			false,
		)

	const lineMaterial =
		new THREE.MeshBasicMaterial({
			color:
				0xffffff,
		})

	return new THREE.Mesh(
			lineGeometry,
			lineMaterial,
		)
}

function rebuildPaletteOverlay() {
	disposePaletteGroup()

	if (
		!palette_enabled.value ||
		palettePoints.length === 0
	) {
		return
	}

	paletteGroup =
		new THREE.Group()

	for (
		const point of
			palettePoints
	) {
		const markerGeometry =
			new THREE.SphereGeometry(
				PALETTE_MARKER_RADIUS,
				16,
				12,
			)

		const markerMaterial =
			new THREE.MeshBasicMaterial({
				color:
					point.hex,
			})

		const marker =
			new THREE.Mesh(
				markerGeometry,
				markerMaterial,
			)

		marker.position.copy(
			point.position,
		)

		paletteGroup.add(
			marker,
		)
	}

	const line =
		createPaletteCurve()

	if (
		line
	) {
		paletteGroup.add(
			line,
		)
	}

	scene.add(
		paletteGroup,
	)
}


// Orbit controls

function setupControls(
	stateOverride = null,
) {
	controls =
		new OrbitControls(
			camera,
			renderer.domElement,
		)

	const state =
		stateOverride ||
		pendingCameraState ||
		loadCameraState()

	if (
		state
	) {
		controls.target.set(
			state.target.x,
			state.target.y,
			state.target.z,
		)
	}

	controls.addEventListener(
		'change',
		handleCameraChange,
	)

	pendingCameraState = null
}

function handleCameraChange() {
	if (
		renderMode.value ===
			'squares' &&
		camera.isOrthographicCamera &&
		material
	) {
		material.size =
			getSquarePointSize()
	}

	if (
		renderMode.value ===
			'splats'
	) {
		sortNeeded = true
	}

	saveCameraState()
}


// Animation

function animate() {
	animationFrame =
		requestAnimationFrame(
			animate,
		)

	controls.update()

	if (
		renderMode.value ===
			'splats' &&
		sortNeeded
	) {
		sortSplats()

		sortNeeded = false
	}

	renderer.render(
		scene,
		camera,
	)
}

function startAnimation() {
	animate()
}


// Tweakpane

function updatePaletteBindingVisibility() {
	for (
		let i = 0;
		i <
			paletteColorBindings.length;
		i++
	) {
		paletteColorBindings[
			i
		].hidden =
			i >=
			palette_size.value
	}
}

function updateShapeBindingVisibility() {
	const isCube =
		shape.value ===
		'cube'

	const isCylinder =
		shape.value ===
		'cylinder'

	const isTorus =
		shape.value ===
		'torus'

	for (
		const binding of
		[
			cubeWidthBinding,
			cubeHeightBinding,
			cubeDepthBinding,
		]
	) {
		if (
			binding
		) {
			binding.hidden =
				!isCube
		}
	}

	for (
		const binding of
		[
			cylinderGapBinding,
			cylinderRadiusBinding,
			cylinderHeightBinding,
		]
	) {
		if (
			binding
		) {
			binding.hidden =
				!isCylinder
		}
	}

	if (
		torusRotationBinding
	) {
		torusRotationBinding.hidden =
			!isTorus
	}
}

function loadPaneState() {
	try {
		const saved =
			localStorage.getItem(
				PANE_STATE_STORAGE_KEY,
			)

		return saved
			? JSON.parse(
				saved,
			)
			: {}
	} catch {
		return {}
	}
}

function getPaneExpanded(
	state,
	key,
) {
	return typeof state[key] ===
		'boolean'
		? state[key]
		: true
}

function trackPaneExpanded(
	key,
	folder,
) {
	folder.on(
		'fold',
		(event) => {
			const state =
				loadPaneState()

			state[key] =
				event.expanded

			try {
				localStorage.setItem(
					PANE_STATE_STORAGE_KEY,
					JSON.stringify(
						state,
					),
				)
			} catch {
				// Ignore unavailable storage.
			}
		},
	)
}

function setupColorPickerToggle(
	binding,
) {
	const button =
		binding.element
			.querySelector(
				'.tp-colswv_b',
			)

	if (
		!button
	) {
		return
	}

	button.addEventListener(
		'pointerdown',
		handleColorPickerPointerDown,
		true,
	)

	button.addEventListener(
		'click',
		handleColorPickerClick,
		true,
	)

	colorPickerToggleButtons.push(
		button,
	)
}

function setupSettingDescriptions(
	targetPane,
) {
	const descriptions = {
		Mode:
			'Chooses between crisp square points and soft Gaussian splats.',

		'Point size':
			'Controls how large each rendered color point appears.',

		'Point density':
			'Sets the grid resolution per axis, so the total point count is density cubed.',

		Shape:
			'Maps the color space onto a cube, cylinder, or torus.',

		'Cube width':
			'Changes the cube size along its horizontal X axis.',

		'Cube height':
			'Changes the cube size along its vertical Y axis.',

		'Cube depth':
			'Changes the cube size along its front-to-back Z axis.',

		'Cylinder gap':
			'Controls the empty radial space through the center of the cylinder.',

		'Cylinder radius':
			'Controls the radial thickness of the cylinder color space.',

		'Cylinder height':
			'Controls the cylinder size along its vertical axis.',

		'Torus rotation':
			'Rotates colors around the torus tube to move dark and light regions inside, outside, up, or down.',

		'Show palette':
			'Shows or hides the palette markers and connecting curve.',

		'Show lattice':
			'Shows or hides the elastic explosion influence on the background cloud.',

		'Tunnel radius':
			'Sets the desired amount of open space around the palette path.',

		Colors:
			'Sets how many palette colors are active in the path.',

		'Influence scale':
			'Sets how far from the palette curve its repulsion can affect the lattice.',

		'Relax steps':
			'Sets how many elastic solver passes are used to settle the point cloud.',

		Repulsion:
			'Controls how strongly the palette curve pushes nearby points away.',

		'Spring strength':
			'Controls how strongly neighboring points preserve their original spacing.',

		'Restore strength':
			'Pulls deformed points back toward their original color-space positions.',

		Projection:
			'Switches between perspective depth and an orthographic view with no perspective shrinking.',

		'Field of view':
			'Controls how wide the perspective camera sees; lower values look more zoomed in.',

		'Orthographic size':
			'Controls how much of the scene fits vertically in the orthographic camera.',

		'Near clipping':
			'Sets how close geometry can be to the camera before it is hidden.',

		'Far culling':
			'Sets the farthest visible distance, allowing the camera to zoom farther out.',
	}

	for (
		const label of
		targetPane.element.querySelectorAll(
			'.tp-lblv_l',
		)
	) {
		const name =
			label.textContent
				.trim()

		const description =
			descriptions[name] ||
			(
				name.startsWith(
					'Color ',
				)
					? 'Chooses one color whose exact color-space position becomes a palette marker.'
					: null
			)

		if (
			!description
		) {
			continue
		}

		const showDescription =
			() => {
				settingHelp.value =
					description
			}

		const handleKeydown =
			(event) => {
				if (
					event.key ===
						'Enter' ||
					event.key ===
						' '
				) {
					event.preventDefault()
					showDescription()
				}
			}

		label.title =
			description

		label.tabIndex = 0
		label.style.cursor =
			'help'

		label.addEventListener(
			'click',
			showDescription,
		)

		label.addEventListener(
			'keydown',
			handleKeydown,
		)

		settingDescriptionLabels.push({
			label,
			showDescription,
			handleKeydown,
		})
	}
}

function handleColorPickerPointerDown(
	event,
) {
	closingColorPickerButton = null

	const button =
		event.target
			.closest?.(
				'.tp-colswv_b',
			)

	const colorControl =
		button
			?.closest(
				'.tp-colv',
			)

	if (
		!button ||
		!colorControl
			?.classList
				.contains(
					'tp-colv-expanded',
				)
	) {
		return
	}

	closingColorPickerButton =
		button

	const activeElement =
		document.activeElement

	if (
		activeElement &&
		colorControl.contains(
			activeElement,
		)
	) {
		activeElement.dispatchEvent(
			new KeyboardEvent(
				'keydown',
				{
					key:
						'Escape',

					bubbles:
						true,
				},
			),
		)
	}
}

function handleColorPickerClick(
	event,
) {
	const button =
		event.target
			.closest?.(
				'.tp-colswv_b',
			)

	if (
		button !==
		closingColorPickerButton
	) {
		return
	}

	event.preventDefault()
	event.stopImmediatePropagation()

	closingColorPickerButton = null
}

function setupPane() {
	const paneState =
		loadPaneState()

	pane =
		new Pane({
			title:
				'Color Space',

			container:
				paneContainer.value,

			expanded:
				getPaneExpanded(
					paneState,
					'root',
				),
		})

	trackPaneExpanded(
		'root',
		pane,
	)


	// Rendering

	const renderingFolder =
		pane.addFolder({
			title:
				'Rendering',

			expanded:
				getPaneExpanded(
					paneState,
					'rendering',
				),
		})

	trackPaneExpanded(
		'rendering',
		renderingFolder,
	)

	renderingFolder
		.addBinding(
			renderMode,
			'value',
			{
				label:
					'Mode',

				options: {
					Squares:
						'squares',

					'Gaussian splats':
						'splats',
				},
			},
		)
		.on(
			'change',
			() => {
				updateRenderMode()
			},
		)

	renderingFolder
		.addBinding(
			dot_size,
			'value',
			{
				label:
					'Point size',

				min:
					0.01,

				max:
					1,

				step:
					0.005,
			},
		)
		.on(
			'change',
			() => {
				updateDotSize()
			},
		)

	renderingFolder
		.addBinding(
			point_density,
			'value',
			{
				label:
					'Point density',

				min:
					5,

				max:
					75,

				step:
					1,
			},
		)
		.on(
			'change',
			(event) => {
				if (
					event.last
				) {
					updateGeometry()
				}
			},
		)


	// Geometry

	const geometryFolder =
		pane.addFolder({
			title:
				'Geometry',

			expanded:
				getPaneExpanded(
					paneState,
					'geometry',
				),
		})

	trackPaneExpanded(
		'geometry',
		geometryFolder,
	)

	const shapeBinding =
		geometryFolder
			.addBinding(
				shape,
				'value',
				{
					label:
						'Shape',

					options: {
						Cube:
							'cube',

						Cylinder:
							'cylinder',

						Torus:
							'torus',
					},
				},
			)

	cubeWidthBinding =
		geometryFolder
			.addBinding(
				cube_width,
				'value',
				{
					label:
						'Cube width',

					min:
						0.25,

					max:
						12,

					step:
						0.05,
				},
			)

	cubeHeightBinding =
		geometryFolder
			.addBinding(
				cube_height,
				'value',
				{
					label:
						'Cube height',

					min:
						0.25,

					max:
						12,

					step:
						0.05,
				},
			)

	cubeDepthBinding =
		geometryFolder
			.addBinding(
				cube_depth,
				'value',
				{
					label:
						'Cube depth',

					min:
						0.25,

					max:
						12,

					step:
						0.05,
				},
			)

	cylinderGapBinding =
		geometryFolder
			.addBinding(
				cylinder_gap,
				'value',
				{
					label:
						'Cylinder gap',

					min:
						0,

					max:
						5,

					step:
						0.01,
				},
			)

	cylinderRadiusBinding =
		geometryFolder
			.addBinding(
				cylinder_radius,
				'value',
				{
					label:
						'Cylinder radius',

					min:
						0.25,

					max:
						10,

					step:
						0.05,
				},
			)

	cylinderHeightBinding =
		geometryFolder
			.addBinding(
				cylinder_height,
				'value',
				{
					label:
						'Cylinder height',

					min:
						0.25,

					max:
						12,

					step:
						0.05,
				},
			)

	torusRotationBinding =
		geometryFolder
			.addBinding(
				torus_rotation,
				'value',
				{
					label:
						'Torus rotation',

					min:
						-180,

					max:
						180,

					step:
						1,
				},
			)

	updateShapeBindingVisibility()

	shapeBinding.on(
		'change',
		() => {
			updateShapeBindingVisibility()

			updateGeometry()
		},
	)

	for (
		const binding of
		[
			cubeWidthBinding,
			cubeHeightBinding,
			cubeDepthBinding,
			cylinderGapBinding,
			cylinderRadiusBinding,
			cylinderHeightBinding,
			torusRotationBinding,
		]
	) {
		binding.on(
			'change',
			(event) => {
				if (
					event.last
				) {
					updateGeometry()
				}
			},
		)
	}


	// Palette

	const paletteFolder =
		pane.addFolder({
			title:
				'Palette',

			expanded:
				getPaneExpanded(
					paneState,
					'palette',
				),
		})

	trackPaneExpanded(
		'palette',
		paletteFolder,
	)

	paletteFolder
		.addBinding(
			palette_enabled,
			'value',
			{
				label:
					'Show palette',
			},
		)
		.on(
			'change',
			() => {
				rebuildPaletteOverlay()
				saveSettings()
			},
		)

	paletteFolder
		.addBinding(
			tunnel_enabled,
			'value',
			{
				label:
					'Show lattice',
			},
		)
		.on(
			'change',
			() => {
				updateGeometry()
			},
		)

	paletteFolder
		.addBinding(
			tunnel_radius,
			'value',
			{
				label:
					'Tunnel radius',

				min:
					0,

				max:
					5,

				step:
					0.01,
			},
		)
		.on(
			'change',
			(event) => {
				if (
					event.last
				) {
					updateGeometry()
				}
			},
		)

	paletteFolder
		.addBinding(
			palette_size,
			'value',
			{
				label:
					'Colors',

				min:
					2,

				max:
					MAX_PALETTE_COLORS,

				step:
					1,
			},
		)
		.on(
			'change',
			(event) => {
				updatePaletteBindingVisibility()

				if (
					event.last
				) {
					updateGeometry()
				}
			},
		)

	paletteColorBindings = []

	for (
		let i = 0;
		i <
			MAX_PALETTE_COLORS;
		i++
	) {
		const key =
			`color${i + 1}`

		const binding =
			paletteFolder
				.addBinding(
					palette_colors,
					key,
					{
						label:
							`Color ${i + 1}`,
					},
				)

		binding.on(
			'change',
			(event) => {
				if (
					event.last
				) {
					updateGeometry()
				}
			},
		)

		setupColorPickerToggle(
			binding,
		)

		paletteColorBindings.push(
			binding,
		)
	}

	updatePaletteBindingVisibility()

	// Elastic lattice

	const latticeFolder =
		pane.addFolder({
			title:
				'Elastic lattice',

			expanded:
				getPaneExpanded(
					paneState,
					'lattice',
				),
		})

	trackPaneExpanded(
		'lattice',
		latticeFolder,
	)

	latticeFolder
		.addBinding(
			tunnel_influence_scale,
			'value',
			{
				label:
					'Influence scale',

				min:
					0.25,

				max:
					6,

				step:
					0.05,
			},
		)
		.on(
			'change',
			(event) => {
				if (
					event.last
				) {
					updateGeometry()
				}
			},
		)

	latticeFolder
		.addBinding(
			lattice_relaxation_steps,
			'value',
			{
				label:
					'Relax steps',

				min:
					1,

				max:
					30,

				step:
					1,
			},
		)
		.on(
			'change',
			(event) => {
				if (
					event.last
				) {
					updateGeometry()
				}
			},
		)

	latticeFolder
		.addBinding(
			lattice_repulsion_strength,
			'value',
			{
				label:
					'Repulsion',

				min:
					0,

				max:
					2,

				step:
					0.01,
			},
		)
		.on(
			'change',
			(event) => {
				if (
					event.last
				) {
					updateGeometry()
				}
			},
		)

	latticeFolder
		.addBinding(
			lattice_spring_strength,
			'value',
			{
				label:
					'Spring strength',

				min:
					0,

				max:
					12,

				step:
					0.01,
			},
		)
		.on(
			'change',
			(event) => {
				if (
					event.last
				) {
					updateGeometry()
				}
			},
		)

	latticeFolder
		.addBinding(
			lattice_restore_strength,
			'value',
			{
				label:
					'Restore strength',

				min:
					0,

				max:
					1,

				step:
					0.005,
			},
		)
		.on(
			'change',
			(event) => {
				if (
					event.last
				) {
					updateGeometry()
				}
			},
		)


	setupSettingDescriptions(
		pane,
	)
}

function updateCameraBindingVisibility() {
	if (
		cameraFovBinding
	) {
		cameraFovBinding.hidden =
			camera_projection.value !==
			'perspective'
	}

	if (
		cameraOrthoSizeBinding
	) {
		cameraOrthoSizeBinding.hidden =
			camera_projection.value !==
			'orthographic'
	}
}

function setupUtilityPane() {
	const paneState =
		loadPaneState()

	utilityPane =
		new Pane({
			title:
				'Tools',

			container:
				utilityPaneContainer.value,

			expanded:
				getPaneExpanded(
					paneState,
					'utilityRoot',
				),
		})

	trackPaneExpanded(
		'utilityRoot',
		utilityPane,
	)


	// Named presets

	const namedPresetFolder =
		utilityPane.addFolder({
			title:
				'Named presets',

			expanded:
				getPaneExpanded(
					paneState,
					'namedPresets',
				),
		})

	trackPaneExpanded(
		'namedPresets',
		namedPresetFolder,
	)

	const namedPresetFolderContent =
		namedPresetFolder.element
			.querySelector(
				'.tp-fldv_c',
			)

	if (
		namedPresetFolderContent &&
		namedPresetContent.value
	) {
		namedPresetFolderContent.append(
			namedPresetContent.value,
		)
	}


	// Preset sharing

	const presetFolder =
		utilityPane.addFolder({
			title:
				'Preset sharing',

			expanded:
				getPaneExpanded(
					paneState,
					'presets',
				),
		})

	trackPaneExpanded(
		'presets',
		presetFolder,
	)

	presetFolder
		.addButton({
			title:
				'Copy share URL',
		})
		.on(
			'click',
			() => {
				copyShareUrl()
			},
		)

	presetFolder
		.addButton({
			title:
				'Copy preset code',
		})
		.on(
			'click',
			() => {
				copyPresetCode()
			},
		)

	presetFolder
		.addButton({
			title:
				'Import URL / code',
		})
		.on(
			'click',
			() => {
				importPreset()
			},
		)


	// Camera

	const cameraFolder =
		utilityPane.addFolder({
			title:
				'Camera',

			expanded:
				getPaneExpanded(
					paneState,
					'camera',
				),
		})

	trackPaneExpanded(
		'camera',
		cameraFolder,
	)

	cameraFolder
		.addBinding(
			camera_projection,
			'value',
			{
				label:
					'Projection',

				options: {
					Perspective:
						'perspective',

					Orthographic:
						'orthographic',
				},
			},
		)
		.on(
			'change',
			() => {
				rebuildCamera()
			},
		)

	cameraFovBinding =
		cameraFolder
			.addBinding(
				camera_fov,
				'value',
				{
					label:
						'Field of view',

					min:
						10,

					max:
						150,

					step:
						1,
				},
			)
			.on(
				'change',
				(event) => {
					if (
						event.last
					) {
						rebuildCamera()
					}
				},
			)

	cameraOrthoSizeBinding =
		cameraFolder
			.addBinding(
				camera_ortho_size,
				'value',
				{
					label:
						'Orthographic size',

					min:
						0.5,

					max:
						50,

					step:
						0.1,
				},
			)
			.on(
				'change',
				(event) => {
					if (
						event.last
					) {
						rebuildCamera()
					}
				},
			)

	cameraFolder
		.addBinding(
			camera_near,
			'value',
			{
				label:
					'Near clipping',

				min:
					0.001,

				max:
					10,

				step:
					0.01,
			},
		)
		.on(
			'change',
			(event) => {
				if (
					event.last
				) {
					rebuildCamera()
				}
			},
		)

	cameraFolder
		.addBinding(
			camera_far,
			'value',
			{
				label:
					'Far culling',

				min:
					10,

				max:
					10000,

				step:
					10,
			},
		)
		.on(
			'change',
			(event) => {
				if (
					event.last
				) {
					rebuildCamera()
				}
			},
		)

	cameraFolder
		.addButton({
			title:
				'Reset camera',
		})
		.on(
			'click',
			() => {
				resetCamera()
			},
		)

	updateCameraBindingVisibility()

	setupSettingDescriptions(
		utilityPane,
	)
}


// Vue lifecycle

onMounted(() => {
	loadSettings()
	loadPresetFromUrl()
	refreshPresetEntries()

	setupScene()
	setupCamera()
	setupRenderer()

	setupPalette()
	setupGeometry()
	setupPoints()

	setupControls()
	setupPane()
	setupUtilityPane()

	startAnimation()
})

onBeforeUnmount(() => {
	saveSettings()

	for (
		const button of
		colorPickerToggleButtons
	) {
		button.removeEventListener(
			'pointerdown',
			handleColorPickerPointerDown,
			true,
		)

		button.removeEventListener(
			'click',
			handleColorPickerClick,
			true,
		)
	}

	colorPickerToggleButtons = []

	for (
		const item of
		settingDescriptionLabels
	) {
		item.label.removeEventListener(
			'click',
			item.showDescription,
		)

		item.label.removeEventListener(
			'keydown',
			item.handleKeydown,
		)
	}

	settingDescriptionLabels = []

	cancelAnimationFrame(
		animationFrame,
	)

	controls
		?.dispose()

	pane
		?.dispose()

	utilityPane
		?.dispose()

	disposePaletteGroup()

	geometry
		?.dispose()

	material
		?.dispose()

	renderer
		?.dispose()
})
</script>


<template>
	<div
		ref="paneContainer"
		class="pane-container"
	></div>

	<div class="utility-container">
		<div class="info-panel">
			<div class="point-count">
				<span>Spawned points</span>

				<strong>
					{{ pointCountDisplay }}
				</strong>
			</div>

			<p>{{ settingHelp }}</p>
		</div>

		<div
			ref="namedPresetContent"
			class="preset-browser-body"
		>
			<div class="active-preset-name">
				<span>Currently open</span>

				<strong>{{ activePresetName }}</strong>
			</div>

				<div class="preset-save-row">
				<input
					v-model="newPresetName"
					type="text"
					placeholder="Preset name"
					aria-label="Preset name"
					@keydown.enter="saveNewPreset"
				>

				<button
					type="button"
					@click="saveNewPreset"
				>
					Save new
				</button>
				</div>

				<div
				v-if="presetEntries.length"
				class="preset-list"
				>
				<div
					v-for="entry in presetEntries"
					:key="`${entry.source}:${entry.name}`"
					class="preset-entry"
				>
					<button
						type="button"
						class="preset-load-button"
						:title="`Load ${entry.name}`"
						@click="loadPresetEntry(entry)"
					>
						<span>{{ entry.name }}</span>

						<small v-if="entry.source === 'default'">
							Default
						</small>
					</button>

					<button
						v-if="entry.source === 'local'"
						type="button"
						class="preset-action-button"
						:title="`Overwrite ${entry.name} with the current settings`"
						@click="overwritePresetEntry(entry)"
					>
						Save over
					</button>

					<button
						v-if="entry.source === 'local'"
						type="button"
						class="preset-delete-button"
						:title="`Delete ${entry.name}`"
						@click="deletePresetEntry(entry)"
					>
						×
					</button>
				</div>
				</div>

				<div
				v-else
				class="preset-empty"
				>
					No saved presets yet.
				</div>
		</div>

		<div
			ref="utilityPaneContainer"
			class="utility-pane-container"
		></div>
	</div>

	<div
		v-if="presetConfirmation.open"
		class="confirmation-backdrop"
		role="presentation"
		@click.self="closePresetConfirmation"
	>
		<div
			class="confirmation-dialog"
			role="dialog"
			aria-modal="true"
			:aria-labelledby="'preset-confirmation-title'"
			@keydown.esc="closePresetConfirmation"
		>
			<h2 id="preset-confirmation-title">
				{{ presetConfirmation.title }}
			</h2>

			<p>{{ presetConfirmation.message }}</p>

			<div class="confirmation-actions">
				<button
					type="button"
					autofocus
					@click="closePresetConfirmation"
				>
					Cancel
				</button>

				<button
					v-if="presetConfirmation.alternateLabel"
					type="button"
					@click="confirmPresetAlternateAction"
				>
					{{ presetConfirmation.alternateLabel }}
				</button>

				<button
					type="button"
					:class="{ danger: presetConfirmation.danger }"
					@click="confirmPresetAction"
				>
					{{ presetConfirmation.confirmLabel }}
				</button>
			</div>
		</div>
	</div>

	<div
		ref="threeContainer"
		class="three-container"
	></div>
</template>


<style scoped>
.three-container {
	width: 100vw;
	height: 100vh;
}

.pane-container {
	position: fixed;
	top: 10px;
	left: 10px;
	z-index: 10;
	width: 280px;
}

.utility-container {
	position: fixed;
	top: 10px;
	right: 10px;
	z-index: 10;
	width: 300px;
}

.info-panel {
	box-sizing: border-box;
	margin-bottom: 8px;
	padding: 10px 12px;
	border-radius: 6px;
	background: hsl(230deg 7% 17%);
	box-shadow: 0 2px 4px rgb(0 0 0 / 20%);
	color: hsl(230deg 7% 75%);
	font-family:
		Roboto Mono,
		Source Code Pro,
		Menlo,
		Courier,
		monospace;
	font-size: 11px;
}

.point-count {
	display: flex;
	justify-content: space-between;
	gap: 12px;
}

.point-count strong {
	color: white;
}

.info-panel p {
	min-height: 2.6em;
	margin: 8px 0 0;
	padding-top: 8px;
	border-top: 1px solid rgb(187 188 196 / 15%);
	line-height: 1.3;
}

.preset-browser-body {
	padding: 0 4px;
}

.active-preset-name {
	display: flex;
	justify-content: space-between;
	gap: 8px;
	margin-bottom: 8px;
	color: hsl(230deg 7% 65%);
	font-size: 11px;
}

.active-preset-name strong {
	min-width: 0;
	overflow: hidden;
	color: hsl(230deg 7% 90%);
	text-overflow: ellipsis;
	white-space: nowrap;
}

.preset-save-row,
.preset-entry {
	display: flex;
	gap: 4px;
}

.preset-save-row input {
	min-width: 0;
	flex: 1;
}

.preset-browser-body input,
.preset-browser-body button {
	box-sizing: border-box;
	min-height: 24px;
	border: 0;
	border-radius: 3px;
	background: hsl(230deg 7% 25%);
	color: hsl(230deg 7% 90%);
	font: inherit;
}

.preset-browser-body input {
	padding: 4px 7px;
	outline: 1px solid rgb(187 188 196 / 12%);
}

.preset-browser-body input:focus {
	outline-color: hsl(211deg 80% 60%);
}

.preset-browser-body button {
	padding: 4px 7px;
	cursor: pointer;
}

.preset-browser-body button:hover,
.preset-browser-body button:focus-visible {
	background: hsl(230deg 7% 32%);
}

.preset-list {
	display: grid;
	max-height: 210px;
	margin-top: 8px;
	overflow-y: auto;
	gap: 4px;
}

.preset-load-button {
	display: flex;
	min-width: 0;
	flex: 1;
	align-items: center;
	justify-content: space-between;
	gap: 6px;
	text-align: left;
}

.preset-load-button span {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.preset-load-button small {
	color: hsl(211deg 70% 70%);
	font-size: 9px;
}

.preset-action-button {
	white-space: nowrap;
}

.preset-delete-button {
	width: 24px;
	padding: 0 !important;
	color: hsl(5deg 80% 72%) !important;
	font-size: 16px !important;
}

.preset-empty {
	margin-top: 8px;
	color: hsl(230deg 7% 55%);
}

.confirmation-backdrop {
	position: fixed;
	inset: 0;
	z-index: 1000;
	display: grid;
	place-items: center;
	padding: 20px;
	background: rgb(0 0 0 / 55%);
}

.confirmation-dialog {
	box-sizing: border-box;
	width: min(400px, 100%);
	padding: 18px;
	border: 1px solid rgb(255 255 255 / 12%);
	border-radius: 8px;
	background: hsl(230deg 7% 17%);
	box-shadow: 0 12px 40px rgb(0 0 0 / 50%);
	color: hsl(230deg 7% 88%);
	font-family:
		Roboto Mono,
		Source Code Pro,
		Menlo,
		Courier,
		monospace;
}

.confirmation-dialog h2 {
	margin: 0;
	color: white;
	font-size: 15px;
}

.confirmation-dialog p {
	margin: 12px 0 18px;
	font-size: 12px;
	line-height: 1.5;
}

.confirmation-actions {
	display: flex;
	justify-content: flex-end;
	gap: 8px;
}

.confirmation-actions button {
	min-height: 28px;
	padding: 5px 12px;
	border: 0;
	border-radius: 4px;
	background: hsl(230deg 7% 27%);
	color: white;
	font: inherit;
	cursor: pointer;
}

.confirmation-actions button:hover,
.confirmation-actions button:focus-visible {
	background: hsl(230deg 7% 36%);
}

.confirmation-actions button:last-child {
	background: hsl(211deg 70% 46%);
}

.confirmation-actions button.danger {
	background: hsl(5deg 65% 45%);
}

:deep(.tp-lblv_l) {
	hyphens: none;
	overflow-wrap: normal;
	word-break: normal;
}

</style>
