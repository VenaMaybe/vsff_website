<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'

import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { Pane } from 'tweakpane'

const threeContainer = ref(null)
const paneContainer = ref(null)

let pane

let renderer
let animationFrame
let camera
let controls
let material

let scene
let geometry
let dots

let basePositions
let baseColors

let sortOrder
let depths

let sortedPositions
let sortedColors

let sortNeeded = true

// Constants
const CAMERA_STORAGE_KEY = 'three-camera-state'
const DOT_SIZE_STORAGE_KEY = 'three-dot-size'

const point_density = ref(50)
const shape = ref('cube') // vs cylinder
const renderMode = ref('squares') // vs splats

const CUBE_SIZE = 5

const cylinder_gap = ref(3)
const CYLINDER_RADIUS = 3
const CYLINDER_HEIGHT = 3

const TORUS_MAJOR_RADIUS = 3
const TORUS_TUBE_RADIUS = 1.25

const savedDotSize = localStorage.getItem(
	DOT_SIZE_STORAGE_KEY,
)

const dot_size = ref(
	savedDotSize !== null
		? Number(savedDotSize)
		: 0.07
)

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

function getLinearAlpha(index) {
	return index /
		(point_density.value - 1)
}

function getCircularAlpha(index) {
	return index /
		point_density.value
}

function getDotPositionCube(i, j, k) {
	const x =
		(
			getLinearAlpha(i) -
			0.5
		) *
		CUBE_SIZE

	const y =
		(
			getLinearAlpha(j) -
			0.5
		) *
		CUBE_SIZE

	const z =
		(
			getLinearAlpha(k) -
			0.5
		) *
		CUBE_SIZE

	return {
		x,
		y,
		z,
	}
}

function getDotPositionCylinder(i, j, k) {
	const radiusAlpha =
		getLinearAlpha(i)

	const heightAlpha =
		getLinearAlpha(j)

	const angleAlpha =
		getCircularAlpha(k)

	const radius =
		radiusAlpha *
		CYLINDER_RADIUS +
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
		CYLINDER_HEIGHT

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

function getDotPositionTorus(i, j, k) {
	const tubeDepth =
		getLinearAlpha(i)

	const tubeAngle =
		getCircularAlpha(j) *
		Math.PI *
		2

	const torusAngle =
		getCircularAlpha(k) *
		Math.PI *
		2

	const tubeRadius =
		tubeDepth *
		TORUS_TUBE_RADIUS

	const ringDistance =
		TORUS_MAJOR_RADIUS +
		Math.cos(tubeAngle) *
		tubeRadius

	const x =
		Math.cos(torusAngle) *
		ringDistance

	const y =
		Math.sin(tubeAngle) *
		tubeRadius

	const z =
		Math.sin(torusAngle) *
		ringDistance

	return {
		x,
		y,
		z,
	}
}

function getDotPosition(i, j, k) {
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

function getDotColorHSL(x, y, z)  {
	// Calculate the percentage alpha between 0.0 and 1.0
	// Using (size - 1) ensures the last item exactly matches colorEnd
	const coords = { // these are the alphas
		x: getLinearAlpha(x),
		y: getLinearAlpha(y),
		z: getLinearAlpha(z),
	}

	// manual lerpingingingignign
	const h = getAxisValue(
		coords,
		hslAxes.h,
	)

	const s = getAxisValue(
		coords,
		hslAxes.s,
	)

	const l = getAxisValue(
		coords,
		hslAxes.l,
	)
	return new THREE.Color().setHSL(h, s, l, THREE.SRGBColorSpace)
	// https://stackoverflow.com/questions/12524623/what-are-the-practical-differences-when-working-with-colors-in-a-linear-vs-a-no
}

function getDotColorHSV(x, y, z) {
	const coords = {
		x: getLinearAlpha(x),
		y: getLinearAlpha(y),
		z: getLinearAlpha(z),
	}

	const h = getAxisValue(
		coords,
		hsvAxes.h,
	)

	const s = getAxisValue(
		coords,
		hsvAxes.s,
	)

	const v = getAxisValue(
		coords,
		hsvAxes.v,
	)

	return hsvToColor(
		h,
		s,
		v,
	)
}

function getAxisValue(coords, axis) {
	const direction = axis[0]
	const axisName = axis[1]

	const value = coords[axisName]

	if (direction === '-') {
		return 1 - value
	}

	return value
}

function hsvToColor(h, s, v) {
	h = h % 1

	const sector = Math.floor(h * 6)
	const fraction = h * 6 - sector

	const p = v * (1 - s)
	const q = v * (1 - fraction * s)
	const t = v * (1 - (1 - fraction) * s)

	let r
	let g
	let b

	switch (sector % 6) {
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

	return new THREE.Color().setRGB(
		r,
		g,
		b,
		THREE.SRGBColorSpace,
	)
}

function resetCamera() {
	camera.position.set(
		0,
		0,
		8,
	)

	controls.target.set(
		0,
		0,
		0,
	)

	controls.update()

	localStorage.removeItem(
		CAMERA_STORAGE_KEY,
	)
}

function updateDotSize() {
	if (material) {
		if (renderMode.value === 'splats') {
			material.uniforms.dotSize.value =
				dot_size.value
		} else {
			material.size =
				dot_size.value
		}
	}

	localStorage.setItem(
		DOT_SIZE_STORAGE_KEY,
		dot_size.value.toString(),
	)
}

function createPointMaterial() {
	if (renderMode.value === 'splats') {
		return createSplatMaterial()
	}

	return createSquareMaterial()
}

function createSquareMaterial() {
	return new THREE.PointsMaterial({
		size: dot_size.value,
		vertexColors: true,
		depthTest: true,
		depthWrite: true,
		transparent: false,
	})
}

function createSplatMaterial() {
	return new THREE.ShaderMaterial({
		uniforms: {
			dotSize: {
				value: dot_size.value,
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

		vertexColors: true,
		transparent: true,
		depthWrite: false,
		blending: THREE.NormalBlending,
	})
}

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
		basePositions.length / 3

	for (
		let i = 0;
		i < pointCount;
		i++
	) {
		const offset =
			i * 3

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

		depths[i] =
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
			sortOrder[i] * 3

		const destination =
			i * 3

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

	geometry.attributes.position.needsUpdate =
		true

	geometry.attributes.color.needsUpdate =
		true
}

function updateRenderMode() {
	if (!dots) {
		return
	}

	material.dispose()

	material =
		createPointMaterial()

	dots.material =
		material

	if (renderMode.value === 'splats') {
		sortNeeded = true
	}
}

function setupScene() {
	scene =
		new THREE.Scene()
}

function setupCamera() {
	camera =
		new THREE.PerspectiveCamera(
			75,
			window.innerWidth /
				window.innerHeight,
			0.1,
			1000,
		)

	const state =
		loadCameraState()

	if (state) {
		camera.position.set(
			state.position.x,
			state.position.y,
			state.position.z,
		)
	} else {
		camera.position.set(
			0,
			0,
			8,
		)
	}
}

function loadCameraState() {
	const saved =
		localStorage.getItem(
			CAMERA_STORAGE_KEY,
		)

	if (!saved) {
		return null
	}

	try {
		const state =
			JSON.parse(saved)

		if (
			!state.position ||
			!state.target
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
	localStorage.setItem(
		CAMERA_STORAGE_KEY,
		JSON.stringify({
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
		}),
	)
}

function setupRenderer() {
	renderer =
		new THREE.WebGLRenderer({
			antialias: true,
		})

	renderer.setSize(
		window.innerWidth,
		window.innerHeight,
	)

	threeContainer.value.appendChild(
		renderer.domElement,
	)
}

function setupGeometry() {
	const positions = []
	const colors = []

	for (
		let i = 0;
		i < point_density.value;
		i++
	) {
		for (
			let j = 0;
			j < point_density.value;
			j++
		) {
			for (
				let k = 0;
				k < point_density.value;
				k++
			) {
				addPoint(
					positions,
					colors,
					i,
					j,
					k,
				)
			}
		}
	}

	setupGeometryBuffers(
		positions,
		colors,
	)
}

function updateGeometry() {
	if (!dots) {
		return
	}

	const oldGeometry =
		geometry

	setupGeometry()

	dots.geometry =
		geometry

	oldGeometry?.dispose()

	if (
		renderMode.value ===
		'splats'
	) {
		sortNeeded = true
	}
}

function addPoint(
	positions,
	colors,
	i,
	j,
	k,
) {
	const position =
		getDotPosition(
			i,
			j,
			k,
		)

	positions.push(
		position.x,
		position.y,
		position.z,
	)

	const color =
		getDotColorHSV(
			i,
			j,
			k,
		)

	colors.push(
		color.r,
		color.g,
		color.b,
	)
}

function updatePointDensity() {
	if (!dots) {
		return
	}

	const oldGeometry =
		geometry

	setupGeometry()

	dots.geometry =
		geometry

	oldGeometry?.dispose()

	if (
		renderMode.value ===
		'splats'
	) {
		sortNeeded = true
	}
}

function setupGeometryBuffers(
	positions,
	colors,
) {
	geometry =
		new THREE.BufferGeometry()

	basePositions =
		new Float32Array(
			positions,
		)

	baseColors =
		new Float32Array(
			colors,
		)

	const pointCount =
		basePositions.length / 3

	sortOrder =
		Array.from(
			{
				length: pointCount,
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

function setupControls() {
	controls =
		new OrbitControls(
			camera,
			renderer.domElement,
		)

	const state =
		loadCameraState()

	if (state) {
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
}

function handleCameraChange() {
	if (
		renderMode.value ===
		'splats'
	) {
		sortNeeded = true
	}

	saveCameraState()
}

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

// Tweaking out
function setupPane() {
	pane = new Pane({
		title: 'Color Space',
		container: paneContainer.value,
	})

	const renderingFolder = pane.addFolder({
		title: 'Rendering',
	})

	renderingFolder.addBinding(
		renderMode,
		'value',
		{
			label: 'Mode',
			options: {
				Squares: 'squares',
				'Gaussian splats': 'splats',
			},
		},
	).on('change', () => {
		updateRenderMode()
	})

	renderingFolder.addBinding(
		dot_size,
		'value',
		{
			label: 'Point size',
			min: 0.01,
			max: 1,
			step: 0.005,
		},
	).on('change', () => {
		updateDotSize()
	})

	renderingFolder.addBinding(
		point_density,
		'value',
		{
			label: 'Point density',
			min: 5,
			max: 75,
			step: 1,
		},
	).on('change', (event) => {
		if (event.last) {
			updatePointDensity()
		}
	})

	const geometryFolder = pane.addFolder({
		title: 'Geometry',
	})

	const shapeBinding =
		geometryFolder.addBinding(
			shape,
			'value',
			{
				label: 'Shape',
				options: {
					Cube: 'cube',
					Cylinder: 'cylinder',
					Torus: 'torus',
				},
			},
		)

	const cylinderGapBinding =
		geometryFolder.addBinding(
			cylinder_gap,
			'value',
			{
				label: 'Cylinder gap',
				min: 0,
				max: 5,
				step: 0.01,
			},
		)

	cylinderGapBinding.hidden =
		shape.value !== 'cylinder'

	shapeBinding.on('change', () => {
		cylinderGapBinding.hidden =
			shape.value !== 'cylinder'

		updateGeometry()
	})

	cylinderGapBinding.on('change', () => {
		updateGeometry()
	})

	const cameraFolder = pane.addFolder({
		title: 'Camera',
	})

	cameraFolder.addButton({
		title: 'Reset camera',
	}).on('click', () => {
		resetCamera()
	})
}

onMounted(() => {
	setupScene()
	setupCamera()
	setupRenderer()
	setupGeometry()
	setupPoints()
	setupControls()
	setupPane()
	startAnimation()
})

onBeforeUnmount(() => {
	cancelAnimationFrame(
		animationFrame,
	)

	controls?.dispose()
	pane?.dispose()
	geometry?.dispose()
	material?.dispose()
	renderer?.dispose()
})
</script>

<template>
	<div
		ref="paneContainer"
		class="pane-container"
	></div>

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
</style>