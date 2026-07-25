import sharp from 'sharp'

const images = [
	{
		input: 'src/assets/images/HardLight@2x.png',
		output: 'src/assets/images/HardLight.webp',
	},
	{
		input: 'src/assets/images/Hue@2x.png',
		output: 'src/assets/images/Hue.webp',
	},
]

for (const image of images) {
	await sharp(image.input)
		.resize({
			width: 1600,
			withoutEnlargement: true,
		})
		.webp({
			quality: 70,
			effort: 6,
		})
		.toFile(image.output)

	console.log(`Created ${image.output}`)
}


/* 
vena@astolfos-rat:~/dev2/vsff_website/frontend$ node scripts/optimize-overlays.mjs
Created src/assets/images/HardLight.webp
Created src/assets/images/Hue.webp
 */