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
	LineSegments2,
} from 'three/addons/lines/LineSegments2.js'
import {
	LineSegmentsGeometry,
} from 'three/addons/lines/LineSegmentsGeometry.js'
import {
	LineMaterial,
} from 'three/addons/lines/LineMaterial.js'

import {
	Pane,
} from 'tweakpane'

import {
	ColorExplorerFlightController,
	FLIGHT_TUNING,
} from '../ColorExplorerFlightController.js'


// Add built-in presets here. Codes can be copied
// from the Color Explorer's "Copy preset" button.

const DEFAULT_PRESETS = [
	{
		"name": 'Default',
		"code": 'color-explorer:eyJ2ZXJzaW9uIjoxLCJzZXR0aW5ncyI6eyJyZW5kZXJNb2RlIjoic3F1YXJlcyIsImRvdFNpemUiOjAuMjA1MDAwMDAwMDAwMDAwMDIsInBvaW50RGVuc2l0eSI6MjQsInNoYXBlIjoiY3ViZSIsImNvbG9yU3BhY2UiOiJoc3YiLCJjYW1lcmFQcm9qZWN0aW9uIjoicGVyc3BlY3RpdmUiLCJjYW1lcmFGb3YiOjc1LCJjYW1lcmFPcnRob1NpemUiOjgsImNhbWVyYU5lYXIiOjAuMSwiY2FtZXJhRmFyIjoxMDAwLCJjYW1lcmEiOnsicG9zaXRpb24iOnsieCI6NC42NTU4NDcwNzY5NDEzMDksInkiOjQuMzkyNjYxMDY4MDEyMTU1LCJ6IjozLjg5NDcxNzAzMzM2OTZ9LCJ0YXJnZXQiOnsieCI6MC45OTYzNTc5NzE3MDc0NDkyLCJ5IjowLjYzMjE0ODg0OTIzMjA4MTUsInoiOjAuNjI4NTExMDEyODU4Mzg1Nn0sInpvb20iOjF9LCJjdWJlV2lkdGgiOjUsImN1YmVIZWlnaHQiOjUsImN1YmVEZXB0aCI6NSwiY3lsaW5kZXJHYXAiOjMsImN5bGluZGVyUmFkaXVzIjozLCJjeWxpbmRlckhlaWdodCI6MywidG9ydXNSb3RhdGlvbiI6MCwicGFsZXR0ZUVuYWJsZWQiOnRydWUsInR1bm5lbEVuYWJsZWQiOnRydWUsImRlZm9ybWF0aW9uTW9kZSI6ImVsYXN0aWMiLCJ0dW5uZWxSYWRpdXMiOjAuMzUsImV4cGxvc2lvbldpZHRoIjowLjM1LCJleHBsb3Npb25TdHJlbmd0aCI6MC43NSwidHVubmVsSW5mbHVlbmNlU2NhbGUiOjIuMjUsImxhdHRpY2VSZWxheGF0aW9uU3RlcHMiOjEwLCJsYXR0aWNlUmVwdWxzaW9uU3RyZW5ndGgiOjAuMTgsImxhdHRpY2VTcHJpbmdTdHJlbmd0aCI6MC4zNSwibGF0dGljZVJlc3RvcmVTdHJlbmd0aCI6MC4wOCwicGFsZXR0ZVNpemUiOjMsInBhbGV0dGVDb2xvcnMiOnsiY29sb3IxIjoiI2ZmNGY4MSIsImNvbG9yMiI6IiNhODU1ZjciLCJjb2xvcjMiOiIjM2I4MmY2IiwiY29sb3I0IjoiIzIyYzU1ZSIsImNvbG9yNSI6IiNmYWNjMTUiLCJjb2xvcjYiOiIjZjk3MzE2IiwiY29sb3I3IjoiIzA2YjZkNCIsImNvbG9yOCI6IiNmZmZmZmYifX19'
	},
	{
		"name": 'Through A Cylinder',
		"code": "color-explorer:eyJ2ZXJzaW9uIjoxLCJzZXR0aW5ncyI6eyJyZW5kZXJNb2RlIjoic3BsYXRzIiwiZG90U2l6ZSI6MC4zNzUsInJlbGF0aW9uUmFkaXVzIjowLjM1LCJpbnNwZWN0aW9uTW9kZSI6InNwb2tlcyIsInNlbGVjdGlvbkVuYWJsZWQiOnRydWUsInBvaW50RGVuc2l0eSI6NTAsInNoYXBlIjoiY3lsaW5kZXIiLCJjb2xvclNwYWNlIjoiaHN2IiwiY2FtZXJhUHJvamVjdGlvbiI6InBlcnNwZWN0aXZlIiwiY2FtZXJhRm92Ijo3NSwiY2FtZXJhT3J0aG9TaXplIjo4LCJjYW1lcmFOZWFyIjowLjEsImNhbWVyYUZhciI6MTAwMCwiY2FtZXJhIjp7InBvc2l0aW9uIjp7IngiOjEwLjI3MDAyNDc1MjA4NjMwOSwieSI6Ni41NjA1MTgxNTM4NzE0MDcsInoiOjMuOTI1NzY5MzMyMDAxODE0M30sInRhcmdldCI6eyJ4IjoxLjIxNzI3OTExMTUwNTUwMjgsInkiOjAuNDIwNzE5NDA4NDU3MjM2NywieiI6MC40MjUyMjg3NTY2NDQwNjM1fSwiem9vbSI6MX0sImN1YmVXaWR0aCI6NSwiY3ViZUhlaWdodCI6NSwiY3ViZURlcHRoIjo1LCJjeWxpbmRlckdhcCI6MywiY3lsaW5kZXJSYWRpdXMiOjMsImN5bGluZGVySGVpZ2h0IjozLCJ0b3J1c1JvdGF0aW9uIjowLCJwYWxldHRlRW5hYmxlZCI6dHJ1ZSwidHVubmVsRW5hYmxlZCI6dHJ1ZSwiZGVmb3JtYXRpb25Nb2RlIjoib3JpZ2luYWwiLCJ0dW5uZWxSYWRpdXMiOjAuMzUsImVsYXN0aWNUdW5uZWxSYWRpdXMiOjAuMzUsIm9yaWdpbmFsVHVubmVsUmFkaXVzIjowLjk1MDAwMDAwMDAwMDAwMDEsImxvY2FsVHVubmVsUmFkaXVzIjowLjM1MDAwMDAwMDAwMDAwMDAzLCJleHBsb3Npb25XaWR0aCI6MC4zNSwiZXhwbG9zaW9uU3RyZW5ndGgiOjAuNzUsInR1bm5lbEluZmx1ZW5jZVNjYWxlIjoyLjI1LCJsYXR0aWNlUmVsYXhhdGlvblN0ZXBzIjoxMCwibGF0dGljZVJlcHVsc2lvblN0cmVuZ3RoIjowLjE3OTk5OTk5OTk5OTk5OTc3LCJsYXR0aWNlU3ByaW5nU3RyZW5ndGgiOjAuMzQ5OTk5OTk5OTk5OTk5NzYsImxhdHRpY2VSZXN0b3JlU3RyZW5ndGgiOjAuMDc5OTk5OTk5OTk5OTk5NzUsInBhbGV0dGVTaXplIjo4LCJwYWxldHRlQ29sb3JzIjp7ImNvbG9yMSI6IiNmZjRmODEiLCJjb2xvcjIiOiIjYTg1NWY3IiwiY29sb3IzIjoiIzNiODJmNiIsImNvbG9yNCI6IiMyMmM1NWUiLCJjb2xvcjUiOiIjZmFjYzE1IiwiY29sb3I2IjoiI2Y5NzMxNiIsImNvbG9yNyI6IiMwNmI2ZDQiLCJjb2xvcjgiOiIjZmZmZmZmIn19fQ"
	},
	{
		"name": "Circles",
		"code": "color-explorer:eyJ2ZXJzaW9uIjoxLCJzZXR0aW5ncyI6eyJyZW5kZXJNb2RlIjoic3BsYXRzIiwiZG90U2l6ZSI6MC4xNTUsInJlbGF0aW9uUmFkaXVzIjowLjM1LCJpbnNwZWN0aW9uTW9kZSI6InNwb2tlcyIsInNlbGVjdGlvbkVuYWJsZWQiOnRydWUsInBvaW50RGVuc2l0eSI6NTgsInNoYXBlIjoiY3ViZSIsImNvbG9yU3BhY2UiOiJoc3YiLCJjYW1lcmFQcm9qZWN0aW9uIjoicGVyc3BlY3RpdmUiLCJjYW1lcmFGb3YiOjc1LCJjYW1lcmFPcnRob1NpemUiOjgsImNhbWVyYU5lYXIiOjAuMSwiY2FtZXJhRmFyIjoxMDAwLCJjYW1lcmEiOnsicG9zaXRpb24iOnsieCI6LTQuNDYyNzM4NzQ0NDUxOTM4LCJ5Ijo4LjE2NDI0NTEzNzk1MjM4NSwieiI6LTcuMzI1NDYxMDM1NzkwNTUxfSwidGFyZ2V0Ijp7IngiOjAuNzg0NDczNTQ4MTUwODc4NCwieSI6MC4xOTI1MDc0OTMyNjEyNzMsInoiOi0wLjQzNjM3NzU3NTEwNzkyMDh9LCJ6b29tIjoxfSwiY3ViZVdpZHRoIjo1LCJjdWJlSGVpZ2h0Ijo1LCJjdWJlRGVwdGgiOjUsImN5bGluZGVyR2FwIjozLCJjeWxpbmRlclJhZGl1cyI6MywiY3lsaW5kZXJIZWlnaHQiOjMsInRvcnVzUm90YXRpb24iOjAsInBhbGV0dGVFbmFibGVkIjpmYWxzZSwidHVubmVsRW5hYmxlZCI6dHJ1ZSwiZGVmb3JtYXRpb25Nb2RlIjoiY29tYmluZWQiLCJ0dW5uZWxSYWRpdXMiOjIuMTIsImVsYXN0aWNUdW5uZWxSYWRpdXMiOjIuMTIsIm9yaWdpbmFsVHVubmVsUmFkaXVzIjoyLjQyLCJsb2NhbFR1bm5lbFJhZGl1cyI6MC4zNDk5OTk5OTk5OTk5OTk5LCJleHBsb3Npb25XaWR0aCI6MC4zNSwiZXhwbG9zaW9uU3RyZW5ndGgiOjAuNzUsInR1bm5lbEluZmx1ZW5jZVNjYWxlIjoyLjI1LCJsYXR0aWNlUmVsYXhhdGlvblN0ZXBzIjoxMCwibGF0dGljZVJlcHVsc2lvblN0cmVuZ3RoIjowLjE4MDAwMDAwMDAwMDAwMDEsImxhdHRpY2VTcHJpbmdTdHJlbmd0aCI6MC4zNDk5OTk5OTk5OTk5OTk2NCwibGF0dGljZVJlc3RvcmVTdHJlbmd0aCI6MC4wNzk5OTk5OTk5OTk5OTk5NywicGFsZXR0ZVNpemUiOjgsInBhbGV0dGVDb2xvcnMiOnsiY29sb3IxIjoiI2ZmNGY4MSIsImNvbG9yMiI6IiNhODU1ZjciLCJjb2xvcjMiOiIjM2I4MmY2IiwiY29sb3I0IjoiIzIyYzU1ZSIsImNvbG9yNSI6IiNmYWNjMTUiLCJjb2xvcjYiOiIjZjk3MzE2IiwiY29sb3I3IjoiIzA5MGMwYyIsImNvbG9yOCI6IiNmZmZmZmYifX19"
	},
	{
		"name": "Cube Destruction",
		"code": "color-explorer:eyJ2ZXJzaW9uIjoxLCJzZXR0aW5ncyI6eyJyZW5kZXJNb2RlIjoic3F1YXJlcyIsImRvdFNpemUiOjAuMDI0OTk5OTk5OTk5OTk5OTgsInBvaW50RGVuc2l0eSI6NzUsInNoYXBlIjoiY3ViZSIsImNhbWVyYVByb2plY3Rpb24iOiJwZXJzcGVjdGl2ZSIsImNhbWVyYUZvdiI6NzUsImNhbWVyYU9ydGhvU2l6ZSI6OCwiY2FtZXJhTmVhciI6MC4xLCJjYW1lcmFGYXIiOjEwMDAsImNhbWVyYSI6eyJwb3NpdGlvbiI6eyJ4IjotOS4yOTE0NTU3MTgyMjAzMzYsInkiOjEwLjczODc4NjkwNjUxNzE2MSwieiI6LTkuNzI5MTIzOTM0MzE3Mjk1fSwidGFyZ2V0Ijp7IngiOjAuMzI4ODU3OTA4ODM3MTQ4MTYsInkiOjAuNjg3ODQ5NTI0MTA2NDQ5NSwieiI6LTQuMjY4MzIxMjgwMTIwNDc5ZS0xN30sInpvb20iOjF9LCJjdWJlV2lkdGgiOjUsImN1YmVIZWlnaHQiOjUsImN1YmVEZXB0aCI6NSwiY3lsaW5kZXJHYXAiOjAsImN5bGluZGVyUmFkaXVzIjozLCJjeWxpbmRlckhlaWdodCI6MywidG9ydXNSb3RhdGlvbiI6MCwicGFsZXR0ZUVuYWJsZWQiOnRydWUsInR1bm5lbEVuYWJsZWQiOnRydWUsInR1bm5lbFJhZGl1cyI6Mi43NywidHVubmVsSW5mbHVlbmNlU2NhbGUiOjMuOTUsImxhdHRpY2VSZWxheGF0aW9uU3RlcHMiOjE0LCJsYXR0aWNlUmVwdWxzaW9uU3RyZW5ndGgiOjEuMTEsImxhdHRpY2VTcHJpbmdTdHJlbmd0aCI6Mi4zNDk5OTk5OTk5OTk5OTk2LCJsYXR0aWNlUmVzdG9yZVN0cmVuZ3RoIjoxLCJwYWxldHRlU2l6ZSI6OCwicGFsZXR0ZUNvbG9ycyI6eyJjb2xvcjEiOiIjNWEzZDNkIiwiY29sb3IyIjoiI2E4NTVmNyIsImNvbG9yMyI6IiMzYjgyZjYiLCJjb2xvcjQiOiIjNDY1NjI2IiwiY29sb3I1IjoiIzY0NTgyYSIsImNvbG9yNiI6IiNmZjY4MDAiLCJjb2xvcjciOiIjMDZiNmQ0IiwiY29sb3I4IjoiIzU0NDk0OSJ9fX0"
	},
	{
		"name": "Infinite Mirror",
		"code": "color-explorer:eyJ2ZXJzaW9uIjoxLCJzZXR0aW5ncyI6eyJyZW5kZXJNb2RlIjoic3F1YXJlcyIsImRvdFNpemUiOjAuMDEsInJlbGF0aW9uUmFkaXVzIjowLjM1LCJpbnNwZWN0aW9uTW9kZSI6InNwb2tlcyIsInNlbGVjdGlvbkVuYWJsZWQiOnRydWUsInBvaW50RGVuc2l0eSI6MzYsInNoYXBlIjoiY3ViZSIsImNvbG9yU3BhY2UiOiJoc3YiLCJjYW1lcmFQcm9qZWN0aW9uIjoicGVyc3BlY3RpdmUiLCJjYW1lcmFGb3YiOjc1LCJjYW1lcmFPcnRob1NpemUiOjgsImNhbWVyYU5lYXIiOjAuMSwiY2FtZXJhRmFyIjoxMDAwLCJjYW1lcmEiOnsicG9zaXRpb24iOnsieCI6OC4zMzA0ODI3MDM3OTU2NjIsInkiOjQuMjUxNjE3MzMzNjU5ODUzLCJ6IjotMTIuNjgwNjEyMDQzNTg4MzgzfSwidGFyZ2V0Ijp7IngiOjAuMTA3MzU0MDY4OTM1Nzg4MTUsInkiOjEuMTc1ODA0OTgxNjg2NzE2OSwieiI6MS4xMTY0MjM5NDY0OTA2NTR9LCJ6b29tIjoxfSwiY3ViZVdpZHRoIjo1LCJjdWJlSGVpZ2h0Ijo1LCJjdWJlRGVwdGgiOjUsImN5bGluZGVyR2FwIjozLCJjeWxpbmRlclJhZGl1cyI6MywiY3lsaW5kZXJIZWlnaHQiOjMsInRvcnVzUm90YXRpb24iOjAsInBhbGV0dGVFbmFibGVkIjp0cnVlLCJ0dW5uZWxFbmFibGVkIjp0cnVlLCJkZWZvcm1hdGlvbk1vZGUiOiJjb21iaW5lZCIsInR1bm5lbFJhZGl1cyI6MC4xOTAwMDAwMDAwMDAwMDAxNCwiZWxhc3RpY1R1bm5lbFJhZGl1cyI6MC4xOTAwMDAwMDAwMDAwMDAxNCwib3JpZ2luYWxUdW5uZWxSYWRpdXMiOjAuMzUwMDAwMDAwMDAwMDAwMSwibG9jYWxUdW5uZWxSYWRpdXMiOjIuNjAyMDg1MjEzOTY1MjEwNmUtMTcsImV4cGxvc2lvbldpZHRoIjowLjM1LCJleHBsb3Npb25TdHJlbmd0aCI6MC43NSwidHVubmVsSW5mbHVlbmNlU2NhbGUiOjIuMjUsImxhdHRpY2VSZWxheGF0aW9uU3RlcHMiOjEwLCJsYXR0aWNlUmVwdWxzaW9uU3RyZW5ndGgiOjEyLCJsYXR0aWNlU3ByaW5nU3RyZW5ndGgiOjEyLCJsYXR0aWNlUmVzdG9yZVN0cmVuZ3RoIjo2Ljc1NSwicGFsZXR0ZVNpemUiOjMsInBhbGV0dGVDb2xvcnMiOnsiY29sb3IxIjoiI2ZmNGY4MSIsImNvbG9yMiI6IiNhODU1ZjciLCJjb2xvcjMiOiIjM2I4MmY2IiwiY29sb3I0IjoiIzIyYzU1ZSIsImNvbG9yNSI6IiNmYWNjMTUiLCJjb2xvcjYiOiIjZjk3MzE2IiwiY29sb3I3IjoiIzA2YjZkNCIsImNvbG9yOCI6IiNmZmZmZmYifX19"
	},
	{
		"name": "The Spire",
		"code": "color-explorer:eyJ2ZXJzaW9uIjoxLCJzZXR0aW5ncyI6eyJyZW5kZXJNb2RlIjoic3F1YXJlcyIsImRvdFNpemUiOjAuMDI1LCJwb2ludERlbnNpdHkiOjc1LCJzaGFwZSI6ImN5bGluZGVyIiwiY2FtZXJhUHJvamVjdGlvbiI6InBlcnNwZWN0aXZlIiwiY2FtZXJhRm92Ijo3NSwiY2FtZXJhT3J0aG9TaXplIjo4LCJjYW1lcmFOZWFyIjowLjEsImNhbWVyYUZhciI6MzU0MCwiY2FtZXJhIjp7InBvc2l0aW9uIjp7IngiOi04LjA2MjMzOTg2NzAyNTY4MywieSI6LTkuNjgyMjk3MjAwMjc2NSwieiI6LTIzLjUxMTMxOTYxNTY1NzE2fSwidGFyZ2V0Ijp7IngiOi0wLjU5NjgzMjQ3MjI5NTc2ODIsInkiOjcuMjk4OTQ2MjM3NzcyODM3LCJ6IjozLjA5MDQ2NTk3MzkzNDgzNDZ9LCJ6b29tIjoxfSwiY3ViZVdpZHRoIjo1LCJjdWJlSGVpZ2h0Ijo1LCJjdWJlRGVwdGgiOjQuOTk5OTk5OTk5OTk5OTk5LCJjeWxpbmRlckdhcCI6MCwiY3lsaW5kZXJSYWRpdXMiOjMsImN5bGluZGVySGVpZ2h0IjoyLjk5OTk5OTk5OTk5OTk5OTYsInRvcnVzUm90YXRpb24iOjAsInBhbGV0dGVFbmFibGVkIjp0cnVlLCJ0dW5uZWxFbmFibGVkIjp0cnVlLCJ0dW5uZWxSYWRpdXMiOjEuNDQsInR1bm5lbEluZmx1ZW5jZVNjYWxlIjozLjk1LCJsYXR0aWNlUmVsYXhhdGlvblN0ZXBzIjoxOSwibGF0dGljZVJlcHVsc2lvblN0cmVuZ3RoIjowLjg4MDAwMDAwMDAwMDAwMDEsImxhdHRpY2VTcHJpbmdTdHJlbmd0aCI6Mi40MDk5OTk5OTk5OTk5OTk3LCJsYXR0aWNlUmVzdG9yZVN0cmVuZ3RoIjoxLCJwYWxldHRlU2l6ZSI6OCwicGFsZXR0ZUNvbG9ycyI6eyJjb2xvcjEiOiIjZmY0ZjgxIiwiY29sb3IyIjoiI2E4NTVmNyIsImNvbG9yMyI6IiMzYjgyZjYiLCJjb2xvcjQiOiIjMjJjNTVlIiwiY29sb3I1IjoiI2ZhY2MxNSIsImNvbG9yNiI6IiNmOTczMTYiLCJjb2xvcjciOiIjMDZiNmQ0IiwiY29sb3I4IjoiI2ZmZmZmZiJ9fX0"
	},
	{
		"name": "Hue Squares",
		"code": "color-explorer:eyJ2ZXJzaW9uIjoxLCJzZXR0aW5ncyI6eyJyZW5kZXJNb2RlIjoic3F1YXJlcyIsImRvdFNpemUiOjAuMDI0OTk5OTk5OTk5OTk5OTgsInBvaW50RGVuc2l0eSI6MjcsInNoYXBlIjoiY3ViZSIsImNhbWVyYVByb2plY3Rpb24iOiJwZXJzcGVjdGl2ZSIsImNhbWVyYUZvdiI6NzUsImNhbWVyYU9ydGhvU2l6ZSI6OCwiY2FtZXJhTmVhciI6MC4xLCJjYW1lcmFGYXIiOjEwMDAsImNhbWVyYSI6eyJwb3NpdGlvbiI6eyJ4IjotMS44NTYwMDU1MzA3Mzk4NTEsInkiOjEuMTgyODkzMTkzODExODI5NCwieiI6Ny41Njg2NjYzNDg3MTMyMTE1fSwidGFyZ2V0Ijp7IngiOjAuNDA0NjMyNDMxMDE0NjAyMywieSI6LTEuNDQwMDE5OTY0Mzk1MzYzMywieiI6MC43MTYxODUzMDY5NTkyMTV9LCJ6b29tIjoxfSwiY3ViZVdpZHRoIjowLjI1LCJjdWJlSGVpZ2h0IjowLjI1LCJjdWJlRGVwdGgiOjEyLCJjeWxpbmRlckdhcCI6MCwiY3lsaW5kZXJSYWRpdXMiOjAuMjUsImN5bGluZGVySGVpZ2h0IjoxMiwidG9ydXNSb3RhdGlvbiI6MCwicGFsZXR0ZUVuYWJsZWQiOnRydWUsInR1bm5lbEVuYWJsZWQiOmZhbHNlLCJ0dW5uZWxSYWRpdXMiOjIuNzcsInR1bm5lbEluZmx1ZW5jZVNjYWxlIjozLjk1LCJsYXR0aWNlUmVsYXhhdGlvblN0ZXBzIjoxNCwibGF0dGljZVJlcHVsc2lvblN0cmVuZ3RoIjoxLjExLCJsYXR0aWNlU3ByaW5nU3RyZW5ndGgiOjIuMzQ5OTk5OTk5OTk5OTk5NiwibGF0dGljZVJlc3RvcmVTdHJlbmd0aCI6MSwicGFsZXR0ZVNpemUiOjgsInBhbGV0dGVDb2xvcnMiOnsiY29sb3IxIjoiIzVhM2QzZCIsImNvbG9yMiI6IiNhODU1ZjciLCJjb2xvcjMiOiIjM2I4MmY2IiwiY29sb3I0IjoiIzQ2NTYyNiIsImNvbG9yNSI6IiM2NDU4MmEiLCJjb2xvcjYiOiIjZmY2ODAwIiwiY29sb3I3IjoiIzA2YjZkNCIsImNvbG9yOCI6IiM1NDQ5NDkifX19"
	},
	{
		"name": "Value Cylinder",
		"code": "color-explorer:eyJ2ZXJzaW9uIjoxLCJzZXR0aW5ncyI6eyJyZW5kZXJNb2RlIjoic3F1YXJlcyIsImRvdFNpemUiOjAuMDM5OTk5OTk5OTk5OTk5OTgsInBvaW50RGVuc2l0eSI6NDAsInNoYXBlIjoiY3lsaW5kZXIiLCJjYW1lcmFQcm9qZWN0aW9uIjoib3J0aG9ncmFwaGljIiwiY2FtZXJhRm92Ijo3NSwiY2FtZXJhT3J0aG9TaXplIjo3LjUsImNhbWVyYU5lYXIiOjAuMSwiY2FtZXJhRmFyIjoyNDAwLCJjYW1lcmEiOnsicG9zaXRpb24iOnsieCI6Mi43NDM2MTAyMTg0MTgzOTE3LCJ5IjozLjMwODY5MDg4OTg2ODk1MDQsInoiOjguMjE0OTkxMzE4NDUxNjE4fSwidGFyZ2V0Ijp7IngiOi0wLjAzMzE4MDU4MDc0MTIzMjA1NiwieSI6MS4yNTU0OTY0ODk5NzQ4MDY3LCJ6IjowLjU3NTkyMjA5MDYxNDcyMTl9LCJ6b29tIjowLjYzMzkwNzgzNjIwMzQ4Mn0sImN1YmVXaWR0aCI6NSwiY3ViZUhlaWdodCI6NSwiY3ViZURlcHRoIjo0Ljk5OTk5OTk5OTk5OTk5OSwiY3lsaW5kZXJHYXAiOjAsImN5bGluZGVyUmFkaXVzIjowLjI1LCJjeWxpbmRlckhlaWdodCI6MTIsInRvcnVzUm90YXRpb24iOjAsInBhbGV0dGVFbmFibGVkIjp0cnVlLCJ0dW5uZWxFbmFibGVkIjpmYWxzZSwidHVubmVsUmFkaXVzIjoyLjc3LCJ0dW5uZWxJbmZsdWVuY2VTY2FsZSI6My45NSwibGF0dGljZVJlbGF4YXRpb25TdGVwcyI6MTQsImxhdHRpY2VSZXB1bHNpb25TdHJlbmd0aCI6MS4xMSwibGF0dGljZVNwcmluZ1N0cmVuZ3RoIjoyLjM0OTk5OTk5OTk5OTk5OTYsImxhdHRpY2VSZXN0b3JlU3RyZW5ndGgiOjEsInBhbGV0dGVTaXplIjo4LCJwYWxldHRlQ29sb3JzIjp7ImNvbG9yMSI6IiM1YTNkM2QiLCJjb2xvcjIiOiIjYTg1NWY3IiwiY29sb3IzIjoiIzNiODJmNiIsImNvbG9yNCI6IiM0NjU2MjYiLCJjb2xvcjUiOiIjNjQ1ODJhIiwiY29sb3I2IjoiI2ZmNjgwMCIsImNvbG9yNyI6IiMwNmI2ZDQiLCJjb2xvcjgiOiIjNTQ0OTQ5In19fQ"
	}
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

const selectedPointInfo =
	ref(null)

const copiedPointHex =
	ref(false)

const presetEntries =
	ref([])

const newPresetName =
	ref('')

const activePresetName =
	ref('None')

const mobilePanel =
	ref(null)

const flightActive =
	ref(false)

const flightSpeedDisplay =
	ref('0.0')

const flightRollDegrees =
	ref(0)

const flightPitchOffset =
	ref(0)

const flightJoystick =
	ref({
		x: 0,
		y: 0,
	})

const presetExportTextarea =
	ref(null)

const presetCodeTextarea =
	ref(null)

const presetCodeDialog =
	ref({
		open: false,
		title: '',
		description: '',
		ariaLabel: '',
		copyLabel: '',
		text: '',
		copied: false,
	})

const presetExportDialog =
	ref({
		open: false,
		text: '',
		count: 0,
		copied: false,
	})

const presetImportDialog =
	ref({
		open: false,
		text: '',
		error: '',
	})

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
let fineSliderCleanups = []
let activeFineSliderFinish = null

let renderer
let animationFrame
let canvasResizeObserver = null
let pendingCanvasResizeFrame = null
let camera
let controls
let flightController = null
let flightViewSettings = null
let flightFrame = 0
let lastAnimationTime = 0
let material
let pendingCameraState = null
let pendingCameraOverridesSavedState = false

let scene
let geometry
let dots


// Splat sorting stuff

let basePositions
let baseColors
let baseOriginalPositions
let originalPositions

let sortOrder
let depths

let sortedPositions
let sortedColors

let sortNeeded = true


// Point inspection

const pointRaycaster =
	new THREE.Raycaster()

const pointPointer =
	new THREE.Vector2()

let pointPointerDownX = 0
let pointPointerDownY = 0
let lastPointPickX = Infinity
let lastPointPickY = Infinity
let pointPickCycleIndex = 0
let selectedPointIndex = -1
let relationLines = null
let copiedPointHexTimer = null


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
let orbitSelectedButton = null
let flyButton = null
let elasticLatticeFolder = null
let originalExplosionFolder = null
let localCutawayFolder = null


// Storage

const CAMERA_STORAGE_KEY =
	'three-camera-state'

const SETTINGS_STORAGE_KEY =
	'color-explorer-settings'

const PRESETS_STORAGE_KEY =
	'color-explorer-presets'

const PRESET_ORDER_STORAGE_KEY =
	'color-explorer-preset-order'

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

const color_space =
	ref('hsv')


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

const deformation_mode =
	ref('elastic')

const tunnel_radius =
	ref(0.35)

const original_tunnel_radius =
	ref(0.35)

const local_tunnel_radius =
	ref(0.35)

const explosion_width =
	ref(0.35)

const explosion_strength =
	ref(0.75)

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

const relation_radius =
	ref(0.35)

const inspection_mode =
	ref('spokes')

const selection_enabled =
	ref(true)

const flight_sensitivity =
	ref(0.5)

const flight_wind_volume =
	ref(1)


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
			'hsv',
			'hsl',
			'rgb',
		].includes(
			settings.colorSpace,
		)
	) {
		color_space.value =
			settings.colorSpace
	}

	if (
		[
			'spokes',
			'stations',
		].includes(
			settings.inspectionMode,
		)
	) {
		inspection_mode.value =
			settings.inspectionMode
	}

	if (
		typeof settings.selectionEnabled ===
			'boolean'
	) {
		selection_enabled.value =
			settings.selectionEnabled
	}

	applySavedNumber(
		flight_sensitivity,
		settings.flightSensitivity,
		0.1,
		2,
	)

	applySavedNumber(
		flight_wind_volume,
		settings.flightWindVolume,
		0,
		1,
	)

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

	if (
		[
			'elastic',
			'original',
			'local',
			'combined',
		].includes(
			settings.deformationMode,
		)
	) {
		deformation_mode.value =
			settings.deformationMode
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
		relation_radius,
		settings.relationRadius,
		0.01,
		3,
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
		settings.elasticTunnelRadius ??
			settings.tunnelRadius,
		0,
		5,
	)

	applySavedNumber(
		original_tunnel_radius,
		settings.originalTunnelRadius ??
			settings.tunnelRadius,
		0,
		5,
	)

	applySavedNumber(
		local_tunnel_radius,
		settings.localTunnelRadius ??
			settings.tunnelRadius,
		0,
		5,
	)

	applySavedNumber(
		explosion_width,
		settings.explosionWidth,
		0.01,
		5,
	)

	applySavedNumber(
		explosion_strength,
		settings.explosionStrength,
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
		12,
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
		12,
	)

	applySavedNumber(
		palette_size,
		settings.paletteSize,
		1,
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
			'hsv',
			'hsl',
			'rgb',
		].includes(
			savedSettings.colorSpace,
		)
	) {
		color_space.value =
			savedSettings.colorSpace
	}

	if (
		[
			'spokes',
			'stations',
		].includes(
			savedSettings.inspectionMode,
		)
	) {
		inspection_mode.value =
			savedSettings.inspectionMode
	}

	if (
		typeof savedSettings.selectionEnabled ===
			'boolean'
	) {
		selection_enabled.value =
			savedSettings.selectionEnabled
	}

	applySavedNumber(
		flight_sensitivity,
		savedSettings.flightSensitivity,
		0.1,
		2,
	)

	applySavedNumber(
		flight_wind_volume,
		savedSettings.flightWindVolume,
		0,
		1,
	)

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

	if (
		[
			'elastic',
			'original',
			'local',
			'combined',
		].includes(
			savedSettings.deformationMode,
		)
	) {
		deformation_mode.value =
			savedSettings.deformationMode
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
		relation_radius,
		savedSettings.relationRadius,
		0.01,
		3,
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
		savedSettings.elasticTunnelRadius ??
			savedSettings.tunnelRadius,
		0,
		5,
	)

	applySavedNumber(
		original_tunnel_radius,
		savedSettings.originalTunnelRadius ??
			savedSettings.tunnelRadius,
		0,
		5,
	)

	applySavedNumber(
		local_tunnel_radius,
		savedSettings.localTunnelRadius ??
			savedSettings.tunnelRadius,
		0,
		5,
	)

	applySavedNumber(
		explosion_width,
		savedSettings.explosionWidth,
		0.01,
		5,
	)

	applySavedNumber(
		explosion_strength,
		savedSettings.explosionStrength,
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
		12,
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
		12,
	)

	applySavedNumber(
		palette_size,
		savedSettings.paletteSize,
		1,
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

		relationRadius:
			relation_radius.value,

		inspectionMode:
			inspection_mode.value,

		selectionEnabled:
			selection_enabled.value,

		flightSensitivity:
			flight_sensitivity.value,

		flightWindVolume:
			flight_wind_volume.value,

		pointDensity:
			point_density.value,

		shape:
			shape.value,

		colorSpace:
			color_space.value,

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

		deformationMode:
			deformation_mode.value,

		tunnelRadius:
			tunnel_radius.value,

		elasticTunnelRadius:
			tunnel_radius.value,

		originalTunnelRadius:
			original_tunnel_radius.value,

		localTunnelRadius:
			local_tunnel_radius.value,

		explosionWidth:
			explosion_width.value,

		explosionStrength:
			explosion_strength.value,

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
		relationRadius: 0.35,
		inspectionMode: 'spokes',
		selectionEnabled: true,
		flightSensitivity: 0.5,
		flightWindVolume: 1,
		pointDensity: 50,
		shape: 'cube',
		colorSpace: 'hsv',
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
		deformationMode: 'elastic',
		tunnelRadius: 0.35,
		elasticTunnelRadius: 0.35,
		originalTunnelRadius: 0.35,
		localTunnelRadius: 0.35,
		explosionWidth: 0.35,
		explosionStrength: 0.75,
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
	const legacyRadius =
		Number.isFinite(
			settings.tunnelRadius,
		)
			? settings.tunnelRadius
			: defaults.tunnelRadius

	return {
		...defaults,
		...settings,

		elasticTunnelRadius:
			Number.isFinite(
				settings.elasticTunnelRadius,
			)
				? settings.elasticTunnelRadius
				: legacyRadius,

		originalTunnelRadius:
			Number.isFinite(
				settings.originalTunnelRadius,
			)
				? settings.originalTunnelRadius
				: legacyRadius,

		localTunnelRadius:
			Number.isFinite(
				settings.localTunnelRadius,
			)
				? settings.localTunnelRadius
				: legacyRadius,

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

function getSavedPresetOrder(
	presets,
) {
	const presetNames =
		Object.keys(
			presets,
		)
	let savedOrder = []

	try {
		const saved =
			JSON.parse(
				localStorage.getItem(
					PRESET_ORDER_STORAGE_KEY,
				) ||
					'[]',
			)

		if (
			Array.isArray(
				saved,
			)
		) {
			savedOrder = saved
		}
	} catch {
		savedOrder = []
	}

	const orderedNames = []
	const includedNames =
		new Set()

	for (
		const name of savedOrder
	) {
		if (
			typeof name === 'string' &&
			Object.prototype.hasOwnProperty.call(
				presets,
				name,
			) &&
			!includedNames.has(
				name,
			)
		) {
			orderedNames.push(
				name,
			)
			includedNames.add(
				name,
			)
		}
	}

	for (
		const name of
			presetNames
	) {
		if (
			!includedNames.has(
				name,
			)
		) {
			orderedNames.unshift(
				name,
			)
			includedNames.add(
				name,
			)
		}
	}

	return orderedNames
}

function storeSavedPresetOrder(
	order,
) {
	try {
		localStorage.setItem(
			PRESET_ORDER_STORAGE_KEY,
			JSON.stringify(
				order,
			),
		)
	} catch {
		// Keep presets usable when storage is restricted.
	}
}

function refreshPresetEntries() {
	const localPresets =
		getSavedPresets()
	const localPresetOrder =
		getSavedPresetOrder(
			localPresets,
		)

	storeSavedPresetOrder(
		localPresetOrder,
	)

	presetEntries.value = [
		...localPresetOrder
			.map(
				(name) => ({
					name,
					settings:
						localPresets[name],
					source: 'local',
				}),
			),

		...DEFAULT_PRESETS.map(
			(preset) => ({
				name: preset.name,
				code: preset.code,
				source: 'default',
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
	const isNewPreset =
		!Object.prototype.hasOwnProperty.call(
			presets,
			name,
		)

	presets[name] =
		getCurrentSettings()

	if (
		storeSavedPresets(
			presets,
		) &&
		isNewPreset
	) {
		const presetOrder =
			getSavedPresetOrder(
				presets,
			)

		storeSavedPresetOrder([
			name,
			...presetOrder.filter(
				(presetName) =>
					presetName !== name,
			),
		])
	}

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

				if (
					storeSavedPresets(
						presets,
					)
				) {
					storeSavedPresetOrder(
						getSavedPresetOrder(
							presets,
						),
					)
				}

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
	if (
		flightActive.value
	) {
		stopFlight({
			restoreViewSettings: false,
			persist: false,
		})
	}

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

	updateDeformationBindingVisibility()

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
			.replace(
				/[\s\u200B-\u200D\uFEFF]/g,
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

function captureSharePreview() {
	return new Promise(
		(resolve, reject) => {
			if (
				!renderer ||
				!scene ||
				!camera
			) {
				reject(
					new Error(
						'The color scene is not ready.',
					),
				)
				return
			}

			const source =
				renderer.domElement
			const preview =
				document.createElement(
					'canvas',
				)
			const previewWidth = 1200
			const previewHeight = 630

			preview.width = previewWidth
			preview.height = previewHeight

			const context =
				preview.getContext(
					'2d',
				)

			if (
				!context ||
				source.width < 1 ||
				source.height < 1
			) {
				reject(
					new Error(
						'The color preview could not be drawn.',
					),
				)
				return
			}

			renderer.render(
				scene,
				camera,
			)

			context.fillStyle = '#000000'
			context.fillRect(
				0,
				0,
				previewWidth,
				previewHeight,
			)

			const scale =
				Math.min(
					previewWidth /
						source.width,
					previewHeight /
						source.height,
				)
			const drawWidth =
				source.width * scale
			const drawHeight =
				source.height * scale

			context.drawImage(
				source,
				(
					previewWidth -
						drawWidth
				) * 0.5,
				(
					previewHeight -
						drawHeight
				) * 0.5,
				drawWidth,
				drawHeight,
			)

			preview.toBlob(
				(blob) => {
					if (
						blob
					) {
						resolve(blob)
					} else {
						reject(
							new Error(
								'The color preview could not be encoded.',
							),
						)
					}
				},
				'image/png',
			)
		},
	)
}

async function createPreviewShareUrl(
	directUrl,
) {
	const preview =
		await captureSharePreview()
	const formData =
		new FormData()

	formData.append(
		'preview',
		preview,
		'color-scene.png',
	)

	const response =
		await fetch(
			'/api/color-previews',
			{
				method: 'POST',
				body: formData,
			},
		)

	if (
		!response.ok
	) {
		throw new Error(
			'The color preview could not be saved.',
		)
	}

	const result =
		await response.json()
	const shareUrl =
		new URL(
			result.sharePath,
			window.location.origin,
		)
	const directSceneUrl =
		new URL(directUrl)

	shareUrl.searchParams.set(
		'preset',
		directSceneUrl.searchParams.get(
			'preset',
		),
	)

	if (
		activePresetName.value &&
		activePresetName.value !==
			'Unsaved scene'
	) {
		shareUrl.searchParams.set(
			'name',
			activePresetName.value,
		)
	}

	return shareUrl.toString()
}

async function copyShareUrl() {
	const directUrl =
		getShareUrl()
	let url = directUrl

	presetCodeDialog.value = {
		open: true,
		title: 'Copy share URL',
		description:
			'Creating a social preview of the current scene…',
		ariaLabel:
			'Current scene share URL',
		copyLabel: 'Copy URL',
		text: url,
		copied: false,
	}

	try {
		url = await createPreviewShareUrl(
			directUrl,
		)

		presetCodeDialog.value = {
			...presetCodeDialog.value,
			description:
				'Anyone who opens this URL will load the current scene, and social posts can show its preview image.',
			text: url,
		}
	} catch {
		presetCodeDialog.value = {
			...presetCodeDialog.value,
			description:
				'The scene URL works, but its preview image could not be saved. You can try Copy share URL again.',
			text: directUrl,
		}
	}

	try {
		await navigator.clipboard.writeText(
			url,
		)

		presetCodeDialog.value = {
			...presetCodeDialog.value,
			copied: true,
		}
	} catch {
		// The centered dialog provides a manual copy path.
	}
}

async function copyPresetCode() {
	const settings =
		getCurrentSettings()
	const code =
		`color-explorer:${encodePreset(
			settings,
		)}`

	// Verify the exact text before showing or copying it.
	decodePreset(
		code,
	)

	presetCodeDialog.value = {
		open: true,
		title: 'Copy current preset',
		description:
			'The full code is shown below. A preset name is optional and does not affect whether this code can be loaded.',
		ariaLabel:
			'Current preset code',
		copyLabel: 'Copy code',
		text: code,
		copied: false,
	}

	try {
		await navigator.clipboard.writeText(
			code,
		)

		presetCodeDialog.value = {
			...presetCodeDialog.value,
			copied: true,
		}
	} catch {
		// The multiline dialog provides a reliable
		// manual copy path on iPadOS.
	}
}

async function copyCurrentPresetCode() {
	const text =
		presetCodeDialog.value.text
	let copied = false

	try {
		await navigator.clipboard.writeText(
			text,
		)
		copied = true
	} catch {
		const textArea =
			presetCodeTextarea.value

		if (
			textArea
		) {
			textArea.focus()
			textArea.select()
			textArea.setSelectionRange(
				0,
				text.length,
			)

			try {
				copied =
					document.execCommand(
						'copy',
					)
			} catch {
				copied = false
			}
		}
	}

	presetCodeDialog.value = {
		...presetCodeDialog.value,
		copied,
	}
}

function closePresetCode() {
	presetCodeDialog.value = {
		...presetCodeDialog.value,
		open: false,
		copied: false,
	}
}

async function exportAllPresets() {
	const localPresetEntries =
		presetEntries.value.filter(
			(entry) =>
				entry.source ===
				'local',
		)
	const exportedPresets =
		localPresetEntries
			.sort(
				(entryA, entryB) =>
					entryA.name.localeCompare(
						entryB.name,
					),
			)
			.map(
				(entry) => ({
					name:
						entry.name,
					code:
						`color-explorer:${encodePreset(
							entry.settings,
						)}`,
				}),
			)

	if (
		exportedPresets.length === 0
	) {
		window.alert(
			'There are no named presets to export.',
		)
		return
	}

	const output =
		JSON.stringify(
			exportedPresets,
			null,
			'\t',
		)

	presetExportDialog.value = {
		open: true,
		text: output,
		count:
			exportedPresets.length,
		copied: false,
	}

	try {
		await navigator.clipboard.writeText(
			output,
		)

		presetExportDialog.value = {
			...presetExportDialog.value,
			copied: true,
		}
	} catch {
		// The dialog remains open so iOS users can
		// copy from its multiline text area.
	}
}

async function copyAllPresetExport() {
	const text =
		presetExportDialog.value.text
	let copied = false

	try {
		await navigator.clipboard.writeText(
			text,
		)
		copied = true
	} catch {
		const textArea =
			presetExportTextarea.value

		if (
			textArea
		) {
			textArea.focus()
			textArea.select()
			textArea.setSelectionRange(
				0,
				text.length,
			)

			try {
				copied =
					document.execCommand(
						'copy',
					)
			} catch {
				copied = false
			}
		}
	}

	presetExportDialog.value = {
		...presetExportDialog.value,
		copied,
	}
}

function closePresetExport() {
	presetExportDialog.value = {
		...presetExportDialog.value,
		open: false,
		copied: false,
	}
}

function toggleMobilePanel(
	panel,
) {
	mobilePanel.value =
		mobilePanel.value === panel
			? null
			: panel
}

function closeMobilePanels() {
	mobilePanel.value = null
}

function importPreset() {
	presetImportDialog.value = {
		open: true,
		text: '',
		error: '',
	}
}

function closePresetImport() {
	presetImportDialog.value = {
		...presetImportDialog.value,
		open: false,
		error: '',
	}
}

function submitPresetImport() {
	try {
		let presetInput =
			presetImportDialog.value.text
				.trim()
		let presetName =
			'Imported preset'

		if (
			!presetInput
		) {
			throw new Error(
				'Paste a preset before loading it.',
			)
		}

		if (
			presetInput.startsWith(
				'{',
			)
		) {
			const exportedEntry =
				JSON.parse(
					presetInput.replace(
						/,\s*$/,
						'',
					),
				)

			if (
				!exportedEntry ||
				typeof exportedEntry.code !==
					'string'
			) {
				throw new Error(
					'Missing preset code',
				)
			}

			presetInput =
				exportedEntry.code

			if (
				typeof exportedEntry.name ===
					'string' &&
				exportedEntry.name.trim()
			) {
				presetName =
					exportedEntry.name.trim()
			}
		}

		const settings =
			decodePreset(
				presetInput,
			)

		closePresetImport()

		openPreset(
			settings,
			presetName,
		)
	} catch (error) {
		presetImportDialog.value = {
			...presetImportDialog.value,
			error:
				error instanceof Error
					? error.message
					: 'That preset is invalid.',
		}
	}
}

function loadPresetFromUrl() {
	const navigationEntry =
		performance
			.getEntriesByType?.(
				'navigation',
			)?.[0]

	if (
		navigationEntry?.type ===
			'reload'
	) {
		return
	}

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
		const settings =
			decodePreset(
				code,
			)
		const completeSettings =
			fillPresetDefaults(
				settings,
			)

		pendingCameraOverridesSavedState =
			Boolean(
				completeSettings &&
				completeSettings.pointDensity <= 40 &&
				isValidCameraState(
					completeSettings.camera,
				),
			)

		openPreset(
			settings,
			'Shared preset',
		)
	} catch {
		pendingCameraOverridesSavedState = false

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

function getDotColorRGB(
	x,
	y,
	z,
) {
	return new THREE.Color()
		.setRGB(
			getLinearAlpha(x),
			getLinearAlpha(y),
			getLinearAlpha(z),
			THREE.SRGBColorSpace,
		)
}

function getDotColor(
	x,
	y,
	z,
) {
	switch (
		color_space.value
	) {
		case 'hsl':
			return getDotColorHSL(
				x,
				y,
				z,
			)

		case 'rgb':
			return getDotColorRGB(
				x,
				y,
				z,
			)

		default:
			return getDotColorHSV(
				x,
				y,
				z,
			)
	}
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

function rgbToHsl(
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
		max - min
	const l =
		(
			max + min
		) * 0.5

	let h = 0
	let s = 0

	if (
		delta !== 0
	) {
		s =
			delta /
			(
				1 -
				Math.abs(
					2 * l - 1,
				)
			)

		if (
			max === r
		) {
			h =
				(
					(
						g - b
					) / delta
				) % 6
		} else if (
			max === g
		) {
			h =
				(
					b - r
				) / delta + 2
		} else {
			h =
				(
					r - g
				) / delta + 4
		}

		h /= 6

		if (
			h < 0
		) {
			h += 1
		}
	}

	return {
		h,
		s,
		l,
	}
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

function hslToCoords(
	h,
	s,
	l,
) {
	const coords = {
		x: 0,
		y: 0,
		z: 0,
	}

	setAxisCoord(
		coords,
		hslAxes.h,
		h,
	)
	setAxisCoord(
		coords,
		hslAxes.s,
		s,
	)
	setAxisCoord(
		coords,
		hslAxes.l,
		l,
	)

	return coords
}

function getPaletteColorPosition(
	hex,
) {
	const rgb =
		hexToRgb(
			hex,
		)

	let coords

	if (
		color_space.value ===
			'rgb'
	) {
		coords = {
			x: rgb.r,
			y: rgb.g,
			z: rgb.b,
		}
	} else if (
		color_space.value ===
			'hsl'
	) {
		const hsl =
			rgbToHsl(
				rgb.r,
				rgb.g,
				rgb.b,
			)

		coords =
			hslToCoords(
				hsl.h,
				hsl.s,
				hsl.l,
			)
	} else {
		const hsv =
			rgbToHsv(
				rgb.r,
				rgb.g,
				rgb.b,
			)

		coords =
			hsvToCoords(
				hsv.h,
				hsv.s,
				hsv.v,
			)
	}

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

	if (
		palettePath.length === 1
	) {
		const point =
			palettePath[0]

		paletteSegments.push({
			ax: point.x,
			ay: point.y,
			az: point.z,
			bx: point.x,
			by: point.y,
			bz: point.z,
			abx: 0,
			aby: 0,
			abz: 0,
			lengthSquared: 1,
			length: 1,
			minX: point.x,
			maxX: point.x,
			minY: point.y,
			maxY: point.y,
			minZ: point.z,
			maxZ: point.z,
			isPoint: true,
		})
	}
}


// Tunnel deformation

function applyOriginalExplosion(
	original,
	radius = original_tunnel_radius.value,
) {
	const deformed =
		new Float32Array(
			original,
		)

	if (
		!tunnel_enabled.value ||
		radius <= 0 ||
		paletteSegments.length === 0
	) {
		return deformed
	}

	const radiusSquared =
		radius * radius

	for (
		let offset = 0;
		offset < original.length;
		offset += 3
	) {
		const px = original[offset]
		const py = original[offset + 1]
		const pz = original[offset + 2]

		let closestDistanceSquared =
			Infinity
		let closestX = 0
		let closestY = 0
		let closestZ = 0
		let closestSegment = null

		for (
			let segmentIndex = 0;
			segmentIndex < paletteSegments.length;
			segmentIndex++
		) {
			const segment =
				paletteSegments[segmentIndex]

			if (
				px < segment.minX - radius ||
				px > segment.maxX + radius ||
				py < segment.minY - radius ||
				py > segment.maxY + radius ||
				pz < segment.minZ - radius ||
				pz > segment.maxZ + radius
			) {
				continue
			}

			const apx = px - segment.ax
			const apy = py - segment.ay
			const apz = pz - segment.az

			const alpha = Math.max(
				0,
				Math.min(
					1,
					(
						apx * segment.abx +
						apy * segment.aby +
						apz * segment.abz
					) / segment.lengthSquared,
				),
			)

			const closestPointX =
				segment.ax + segment.abx * alpha
			const closestPointY =
				segment.ay + segment.aby * alpha
			const closestPointZ =
				segment.az + segment.abz * alpha

			const dx = px - closestPointX
			const dy = py - closestPointY
			const dz = pz - closestPointZ
			const distanceSquared =
				dx * dx + dy * dy + dz * dz

			if (
				distanceSquared <
				closestDistanceSquared
			) {
				closestDistanceSquared =
					distanceSquared
				closestX = closestPointX
				closestY = closestPointY
				closestZ = closestPointZ
				closestSegment = segment
			}
		}

		if (
			closestDistanceSquared >=
			radiusSquared ||
			!closestSegment
		) {
			continue
		}

		let dx = px - closestX
		let dy = py - closestY
		let dz = pz - closestZ
		let distance =
			Math.sqrt(
				closestDistanceSquared,
			)

		if (
			distance < 0.000001
		) {
			if (
				closestSegment.isPoint
			) {
				dx = 0
				dy = 1
				dz = 0
			} else if (
				Math.abs(
					closestSegment.abx /
					closestSegment.length,
				) < 0.9
			) {
				dx = 0
				dy = closestSegment.abz
				dz = -closestSegment.aby
			} else {
				dx = -closestSegment.abz
				dy = 0
				dz = closestSegment.abx
			}

			distance =
				Math.sqrt(
					dx * dx +
					dy * dy +
					dz * dz,
				)
		}

		const scale =
			radius / distance

		deformed[offset] =
			closestX + dx * scale
		deformed[offset + 1] =
			closestY + dy * scale
		deformed[offset + 2] =
			closestZ + dz * scale
	}

	return deformed
}

function applyLocalCutaway(
	original,
	colors,
	startingPositions = original,
	radius = local_tunnel_radius.value,
) {
	const maximumLength =
		original.length
	const deformed =
		new Float32Array(
			maximumLength,
		)
	const visibleColors =
		new Float32Array(
			maximumLength,
		)
	const visibleOriginals =
		new Float32Array(
			maximumLength,
		)

	const width =
		explosion_width.value
	const outerRadius =
		radius + width
	const outerRadiusSquared =
		outerRadius * outerRadius
	const blendBand =
		Math.min(
			0.15,
			Math.max(
				0.02,
				width * 0.25,
			),
		)

	let writeOffset = 0

	for (
		let offset = 0;
		offset < original.length;
		offset += 3
	) {
		const px = original[offset]
		const py = original[offset + 1]
		const pz = original[offset + 2]

		let nearestDistanceSquared =
			Infinity
		let nearestDirectionX = 0
		let nearestDirectionY = 1
		let nearestDirectionZ = 0
		let nearestSegment = null

		for (
			let segmentIndex = 0;
			segmentIndex < paletteSegments.length;
			segmentIndex++
		) {
			const segment =
				paletteSegments[segmentIndex]

			if (
				px < segment.minX - outerRadius ||
				px > segment.maxX + outerRadius ||
				py < segment.minY - outerRadius ||
				py > segment.maxY + outerRadius ||
				pz < segment.minZ - outerRadius ||
				pz > segment.maxZ + outerRadius
			) {
				continue
			}

			const apx = px - segment.ax
			const apy = py - segment.ay
			const apz = pz - segment.az
			const alpha = Math.max(
				0,
				Math.min(
					1,
					(
						apx * segment.abx +
						apy * segment.aby +
						apz * segment.abz
					) / segment.lengthSquared,
				),
			)
			const dx =
				px -
				(
					segment.ax +
					segment.abx * alpha
				)
			const dy =
				py -
				(
					segment.ay +
					segment.aby * alpha
				)
			const dz =
				pz -
				(
					segment.az +
					segment.abz * alpha
				)
			const distanceSquared =
				dx * dx + dy * dy + dz * dz

			if (
				distanceSquared <
				nearestDistanceSquared
			) {
				nearestDistanceSquared =
					distanceSquared
				nearestDirectionX = dx
				nearestDirectionY = dy
				nearestDirectionZ = dz
				nearestSegment = segment
			}
		}

		if (
			nearestDistanceSquared <
			radius * radius
		) {
			continue
		}

		let outputX = startingPositions[offset]
		let outputY = startingPositions[offset + 1]
		let outputZ = startingPositions[offset + 2]

		if (
			nearestDistanceSquared <
				outerRadiusSquared &&
			nearestSegment
		) {
			const nearestDistance =
				Math.sqrt(
					nearestDistanceSquared,
				)
			let blendedX = 0
			let blendedY = 0
			let blendedZ = 0
			let totalWeight = 0

			for (
				let segmentIndex = 0;
				segmentIndex < paletteSegments.length;
				segmentIndex++
			) {
				const segment =
					paletteSegments[segmentIndex]
				const apx = px - segment.ax
				const apy = py - segment.ay
				const apz = pz - segment.az
				const alpha = Math.max(
					0,
					Math.min(
						1,
						(
							apx * segment.abx +
							apy * segment.aby +
							apz * segment.abz
						) / segment.lengthSquared,
					),
				)
				let dx =
					px -
					(
						segment.ax +
						segment.abx * alpha
					)
				let dy =
					py -
					(
						segment.ay +
						segment.aby * alpha
					)
				let dz =
					pz -
					(
						segment.az +
						segment.abz * alpha
					)
				const distance =
					Math.sqrt(
						dx * dx +
						dy * dy +
						dz * dz,
					)

				if (
					distance >
						nearestDistance +
						blendBand ||
					distance >= outerRadius
				) {
					continue
				}

				if (
					distance > 0.000001
				) {
					dx /= distance
					dy /= distance
					dz /= distance
				} else {
					continue
				}

				const blendAlpha =
					Math.min(
						1,
						(
							distance -
							nearestDistance
						) / blendBand,
					)
				const weight =
					1 -
					blendAlpha *
						blendAlpha *
						(
							3 -
							2 * blendAlpha
						)

				blendedX += dx * weight
				blendedY += dy * weight
				blendedZ += dz * weight
				totalWeight += weight
			}

			let directionLength =
				Math.sqrt(
					blendedX * blendedX +
					blendedY * blendedY +
					blendedZ * blendedZ,
				)

			if (
				totalWeight <= 0 ||
				directionLength < 0.000001
			) {
				blendedX = nearestDirectionX
				blendedY = nearestDirectionY
				blendedZ = nearestDirectionZ
				directionLength =
					Math.sqrt(
						blendedX * blendedX +
						blendedY * blendedY +
						blendedZ * blendedZ,
					)
			}

			if (
				directionLength < 0.000001
			) {
				if (
					nearestSegment.isPoint
				) {
					blendedX = 0
					blendedY = 1
					blendedZ = 0
				} else if (
					Math.abs(
						nearestSegment.abx /
						nearestSegment.length,
					) < 0.9
				) {
					blendedX = 0
					blendedY = nearestSegment.abz
					blendedZ = -nearestSegment.aby
				} else {
					blendedX = -nearestSegment.abz
					blendedY = 0
					blendedZ = nearestSegment.abx
				}

				directionLength =
					Math.sqrt(
						blendedX * blendedX +
						blendedY * blendedY +
						blendedZ * blendedZ,
					)
			}

			const falloffAlpha =
				Math.max(
					0,
					Math.min(
						1,
						(
							nearestDistance - radius
						) / width,
					),
				)
			const falloff =
				1 -
				falloffAlpha *
					falloffAlpha *
					(
						3 -
						2 * falloffAlpha
					)
			const displacement =
				explosion_strength.value *
				falloff

			outputX +=
				blendedX /
				directionLength *
				displacement
			outputY +=
				blendedY /
				directionLength *
				displacement
			outputZ +=
				blendedZ /
				directionLength *
				displacement
		}

		deformed[writeOffset] = outputX
		deformed[writeOffset + 1] = outputY
		deformed[writeOffset + 2] = outputZ
		visibleColors[writeOffset] = colors[offset]
		visibleColors[writeOffset + 1] = colors[offset + 1]
		visibleColors[writeOffset + 2] = colors[offset + 2]
		visibleOriginals[writeOffset] = original[offset]
		visibleOriginals[writeOffset + 1] = original[offset + 1]
		visibleOriginals[writeOffset + 2] = original[offset + 2]
		writeOffset += 3
	}

	return {
		positions:
			deformed.subarray(
				0,
				writeOffset,
			),

		colors:
			visibleColors.subarray(
				0,
				writeOffset,
			),

		originals:
			visibleOriginals.subarray(
				0,
				writeOffset,
			),
	}
}

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
	radius = tunnel_radius.value,
) {
	let current =
		new Float32Array(
			original,
		)

	if (
		!tunnel_enabled.value ||
		radius <= 0 ||
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
		radius *
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
					segment.isPoint
				) {
					dx = 0
					dy = 1
					dz = 0
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
					radius *
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

function updateFlyButton() {
	if (
		flyButton
	) {
		flyButton.title =
			flightActive.value
				? 'Stop flying'
				: 'Fly'
	}
}

function collapseFlightPanes() {
	if (
		pane
	) {
		pane.expanded = false
	}

	if (
		utilityPane
	) {
		utilityPane.expanded = false
	}

	const paneState =
		loadPaneState()

	paneState.root = false
	paneState.utilityRoot = false

	try {
		localStorage.setItem(
			PANE_STATE_STORAGE_KEY,
			JSON.stringify(
				paneState,
			),
		)
	} catch {
		// Keep flight available when storage is restricted.
	}
}

function startFlight() {
	if (
		flightActive.value ||
		!camera ||
		!controls ||
		!flightController
	) {
		return
	}

	// Unlock Web Audio directly from the initiating tap.
	flightController.primeAudio()

	flightViewSettings = {
		projection:
			camera_projection.value,
		fov:
			camera_fov.value,
		near:
			camera_near.value,
	}

	if (
		camera_projection.value ===
			'orthographic'
	) {
		camera_projection.value =
			'perspective'
		rebuildCamera()
	}

	controls.enabled = false
	camera.near = 0.001

	if (
		camera.isPerspectiveCamera
	) {
		camera.fov =
			Math.max(
				camera.fov,
				FLIGHT_TUNING
					.minimumFlightFov,
			)
	}

	camera.updateProjectionMatrix()
	flightController.setCamera(
		camera,
	)
	flightController.setJoystickSensitivity(
		flight_sensitivity.value,
	)
	flightController.setWindVolume(
		flight_wind_volume.value,
	)
	flightController.start(
		controls.target,
	)
	flightActive.value = true
	document.documentElement
		.classList.add(
			'color-explorer-flight-active',
		)
	flightFrame = 0
	lastAnimationTime =
		performance.now()
	mobilePanel.value = null
	collapseFlightPanes()
	clearPointSelection()
	updateFlyButton()
	updateOrbitSelectedButton()
	sortNeeded = true
}

function stopFlight({
	restoreViewSettings = true,
	persist = true,
} = {}) {
	if (
		!flightActive.value
	) {
		return
	}

	const direction =
		flightController
			?.getDirection() ||
			new THREE.Vector3(0, 0, -1)

	flightController?.stop()
	flightActive.value = false
	document.documentElement
		.classList.remove(
			'color-explorer-flight-active',
		)
	flightJoystick.value = {
		x: 0,
		y: 0,
	}
	flightSpeedDisplay.value =
		'0.0'
	flightRollDegrees.value = 0
	flightPitchOffset.value = 0

	if (
		controls &&
		camera
	) {
		controls.enabled = true
		controls.target
			.copy(
				camera.position,
			)
			.addScaledVector(
				direction,
				0.6,
			)
	}

	if (
		restoreViewSettings &&
		flightViewSettings
	) {
		camera_projection.value =
			flightViewSettings.projection
		camera_fov.value =
			flightViewSettings.fov
		camera_near.value =
			flightViewSettings.near

		const needsRebuild =
			(
				camera_projection.value ===
					'orthographic'
			) !==
			Boolean(
				camera?.isOrthographicCamera,
			)

		if (
			needsRebuild
		) {
			rebuildCamera()
		} else if (
			camera
		) {
			camera.near =
				camera_near.value

			if (
				camera.isPerspectiveCamera
			) {
				camera.fov =
					camera_fov.value
			}

			camera.updateProjectionMatrix()
			controls?.update()
		}
	}

	flightViewSettings = null
	updateFlyButton()
	updateOrbitSelectedButton()
	sortNeeded = true

	if (
		persist
	) {
		saveCameraState()
		saveSettings()
	}
}

function toggleFlight() {
	if (
		flightActive.value
	) {
		stopFlight()
	} else {
		startFlight()
	}
}

function updateFlightJoystick(
	event,
) {
	const bounds =
		event.currentTarget
			.getBoundingClientRect()
	const radius =
		Math.max(
			bounds.width * 0.315,
			1,
		)
	const x =
		THREE.MathUtils.clamp(
			(
				event.clientX -
				(
					bounds.left +
					bounds.width * 0.5
				)
			) / radius,
			-1,
			1,
		)
	const y =
		THREE.MathUtils.clamp(
			(
				event.clientY -
				(
					bounds.top +
					bounds.height * 0.5
				)
			) / radius,
			-1,
			1,
		)

	flightJoystick.value = {
		x,
		y,
	}
	flightController?.setJoystick(
		x,
		-y,
	)
}

function handleFlightJoystickDown(
	event,
) {
	event.preventDefault()
	event.currentTarget
		.setPointerCapture(
			event.pointerId,
		)
	updateFlightJoystick(
		event,
	)
}

function handleFlightJoystickMove(
	event,
) {
	if (
		event.currentTarget
			.hasPointerCapture(
				event.pointerId,
			)
	) {
		event.preventDefault()
		updateFlightJoystick(
			event,
		)
	}
}

function handleFlightJoystickUp(
	event,
) {
	event.preventDefault()

	if (
		event.currentTarget
			.hasPointerCapture(
				event.pointerId,
			)
	) {
		event.currentTarget
			.releasePointerCapture(
				event.pointerId,
			)
	}

	flightJoystick.value = {
		x: 0,
		y: 0,
	}
	flightController?.setJoystick(
		0,
		0,
	)
}

function handleFlightBoost(
	event,
	boosting,
) {
	event.preventDefault()

	if (
		boosting
	) {
		event.currentTarget
			.setPointerCapture(
				event.pointerId,
			)
	}

	flightController?.setBoosting(
		boosting,
	)
}

function handleFlightBoostTouch(
	boosting,
) {
	flightController?.setBoosting(
		boosting,
	)
}

function updateFlightProximity() {
	if (
		!flightController ||
		!basePositions ||
		!camera
	) {
		return
	}

	const pointCount =
		basePositions.length / 3
	const stride =
		Math.max(
			1,
			Math.ceil(
				pointCount / 150000,
			),
		)
	const phase =
		flightFrame % stride
	let nearestDistanceSquared =
		Infinity

	for (
		let offset = phase * 3;
		offset < basePositions.length;
		offset += 3 * stride
	) {
		const dx =
			basePositions[offset] -
			camera.position.x
		const dy =
			basePositions[offset + 1] -
			camera.position.y
		const dz =
			basePositions[offset + 2] -
			camera.position.z
		const distanceSquared =
			dx * dx +
			dy * dy +
			dz * dz

		if (
			distanceSquared <
				nearestDistanceSquared
		) {
			nearestDistanceSquared =
				distanceSquared
		}
	}

	const distance =
		Math.sqrt(
			nearestDistanceSquared,
		)
	const innerDistance =
		Math.max(
			0.012,
			dot_size.value * 0.35,
		)
	const outerDistance =
		Math.max(
			0.16,
			dot_size.value * 1.8,
		)
	const normalizedDistance =
		THREE.MathUtils.clamp(
			(
				distance -
				innerDistance
			) /
			(
				outerDistance -
				innerDistance
			),
			0,
			1,
		)
	const smoothDistance =
		normalizedDistance *
		normalizedDistance *
		(
			3 -
			2 * normalizedDistance
		)

	flightController.setProximity(
		1 - smoothDistance,
	)
}

function resetCamera() {
	if (
		flightActive.value
	) {
		stopFlight({
			restoreViewSettings: false,
			persist: false,
		})
	}

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

	const savedCameraState =
		loadCameraState()
	const state =
		stateOverride ||
		(
			pendingCameraOverridesSavedState
				? pendingCameraState
				: savedCameraState ||
					pendingCameraState
		)

	pendingCameraOverridesSavedState = false

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

	return state
}

function rebuildCamera() {
	if (
		flightActive.value
	) {
		stopFlight({
			restoreViewSettings: false,
			persist: false,
		})
	}

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

	flightController?.setCamera(
		camera,
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
	const width =
		threeContainer.value.clientWidth ||
		window.innerWidth
	const height =
		threeContainer.value.clientHeight ||
		window.innerHeight

	renderer =
		new THREE.WebGLRenderer({
			antialias:
				true,
		})

	renderer.setSize(
		width,
		height,
	)

	if (
		relationLines
	) {
		relationLines.material
			.resolution
			.set(
				width,
				height,
			)
	}

	threeContainer
		.value
		.appendChild(
			renderer.domElement,
		)

	renderer.domElement
		.addEventListener(
			'pointerdown',
			handlePointPointerDown,
		)

	renderer.domElement
		.addEventListener(
			'pointerup',
			handlePointPointerUp,
		)
}

function handleWindowResize() {
	if (
		!renderer ||
		!camera ||
		!threeContainer.value
	) {
		return
	}

	const width =
		Math.max(
			threeContainer.value.clientWidth ||
				window.innerWidth,
			1,
		)
	const height =
		Math.max(
			threeContainer.value.clientHeight ||
				window.innerHeight,
			1,
		)
	const aspect =
		width / Math.max(
			height,
			1,
		)

	renderer.setSize(
		width,
		height,
	)

	if (
		camera.isPerspectiveCamera
	) {
		camera.aspect = aspect
	} else {
		const halfHeight =
			camera_ortho_size.value *
			0.5
		const halfWidth =
			halfHeight * aspect

		camera.left = -halfWidth
		camera.right = halfWidth
		camera.top = halfHeight
		camera.bottom = -halfHeight
	}

	camera.updateProjectionMatrix()

	if (
		relationLines
	) {
		relationLines.material
			.resolution
			.set(
				width,
				height,
			)
	}

	if (
		renderMode.value ===
			'squares' &&
		material
	) {
		material.size =
			getSquarePointSize()
	}

	sortNeeded = true
}

function scheduleCanvasResize() {
	if (
		pendingCanvasResizeFrame !==
		null
	) {
		return
	}

	pendingCanvasResizeFrame =
		requestAnimationFrame(
			() => {
				pendingCanvasResizeFrame =
					null
				handleWindowResize()
			},
		)
}

function setupCanvasResizeTracking() {
	if (
		typeof ResizeObserver !==
			'undefined' &&
		threeContainer.value
	) {
		canvasResizeObserver =
			new ResizeObserver(
				scheduleCanvasResize,
			)

		canvasResizeObserver.observe(
			threeContainer.value,
		)

		canvasResizeObserver.observe(
			document.documentElement,
		)
	}

	window.visualViewport
		?.addEventListener(
			'resize',
			scheduleCanvasResize,
		)

	scheduleCanvasResize()
}


// Cloud geometry

function setupGeometry() {
	const density =
		point_density.value

	const pointCount =
		density *
		density *
		density

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
					getDotColor(
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

	let positions =
		originalPositions

	let visibleColors =
		colors

	let visibleOriginals =
		originalPositions

	if (
		tunnel_enabled.value &&
		paletteSegments.length > 0
	) {
		if (
			deformation_mode.value ===
				'elastic'
		) {
			positions =
				relaxPaletteLattice(
					originalPositions,
					density,
				)
		} else if (
			deformation_mode.value ===
				'original'
		) {
			positions =
				applyOriginalExplosion(
					originalPositions,
				)
		} else if (
			deformation_mode.value ===
				'local'
		) {
			const cutaway =
				applyLocalCutaway(
					originalPositions,
					colors,
				)

			positions =
				cutaway.positions
			visibleColors =
				cutaway.colors
			visibleOriginals =
				cutaway.originals
		} else {
			const elasticPositions =
				relaxPaletteLattice(
					originalPositions,
					density,
					tunnel_radius.value,
				)
			const originalExplosionPositions =
				applyOriginalExplosion(
					originalPositions,
					original_tunnel_radius.value,
				)
			const combinedPositions =
				new Float32Array(
					originalPositions.length,
				)

			for (
				let offset = 0;
				offset < originalPositions.length;
				offset++
			) {
				combinedPositions[offset] =
					elasticPositions[offset] +
					originalExplosionPositions[offset] -
					originalPositions[offset]
			}

			const cutaway =
				applyLocalCutaway(
					originalPositions,
					colors,
					combinedPositions,
					local_tunnel_radius.value,
				)

			positions = cutaway.positions
			visibleColors = cutaway.colors
			visibleOriginals = cutaway.originals
		}
	}

	pointCountDisplay.value =
		(
			positions.length /
			3
		).toLocaleString()

	setupGeometryBuffers(
		positions,
		visibleColors,
		visibleOriginals,
	)
}

function setupGeometryBuffers(
	positions,
	colors,
	originals,
) {
	geometry =
		new THREE.BufferGeometry()

	basePositions =
		positions

	baseColors =
		colors

	baseOriginalPositions =
		originals

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

function disposeRelationLines() {
	if (
		!relationLines
	) {
		return
	}

	scene.remove(
		relationLines,
	)

	relationLines.geometry
		.dispose()
	relationLines.material
		.dispose()

	relationLines = null
}

function clearPointSelection() {
	selectedPointIndex = -1
	selectedPointInfo.value = null
	copiedPointHex.value = false
	disposeRelationLines()
	updateOrbitSelectedButton()
}

function rebuildRelationLines() {
	disposeRelationLines()

	if (
		selectedPointIndex < 0 ||
		!basePositions ||
		!baseOriginalPositions
	) {
		return
	}

	const selectedOffset =
		selectedPointIndex * 3
	const originalX =
		baseOriginalPositions[
			selectedOffset
		]
	const originalY =
		baseOriginalPositions[
			selectedOffset + 1
		]
	const originalZ =
		baseOriginalPositions[
			selectedOffset + 2
		]
	const radiusSquared =
		relation_radius.value *
		relation_radius.value

	const neighborIndexes = []

	for (
		let offset = 0;
		offset < baseOriginalPositions.length;
		offset += 3
	) {
		if (
			offset === selectedOffset
		) {
			continue
		}

		const dx =
			baseOriginalPositions[offset] -
			originalX
		const dy =
			baseOriginalPositions[offset + 1] -
			originalY
		const dz =
			baseOriginalPositions[offset + 2] -
			originalZ

		if (
			dx * dx +
				dy * dy +
				dz * dz <=
			radiusSquared
		) {
			neighborIndexes.push(
				offset / 3,
			)
		}
	}

	if (
		neighborIndexes.length === 0
	) {
		return
	}

	const linePositions =
		new Float32Array(
			neighborIndexes.length * 6,
		)
	let writeOffset = 0

	if (
		inspection_mode.value ===
			'stations'
	) {
		let route

		if (
			neighborIndexes.length <=
			2500
		) {
			const remaining =
				neighborIndexes.slice()

			route = [
				selectedPointIndex,
			]

			while (
				remaining.length > 0
			) {
				const currentIndex =
					route[
						route.length - 1
					]
				const currentOffset =
					currentIndex * 3
				let nearestArrayIndex = 0
				let nearestDistanceSquared =
					Infinity

				for (
					let i = 0;
					i < remaining.length;
					i++
				) {
					const candidateOffset =
						remaining[i] * 3
					const dx =
						baseOriginalPositions[candidateOffset] -
						baseOriginalPositions[currentOffset]
					const dy =
						baseOriginalPositions[candidateOffset + 1] -
						baseOriginalPositions[currentOffset + 1]
					const dz =
						baseOriginalPositions[candidateOffset + 2] -
						baseOriginalPositions[currentOffset + 2]
					const distanceSquared =
						dx * dx +
						dy * dy +
						dz * dz

					if (
						distanceSquared <
						nearestDistanceSquared
					) {
						nearestDistanceSquared =
							distanceSquared
						nearestArrayIndex = i
					}
				}

				route.push(
					remaining[
						nearestArrayIndex
					],
				)

				remaining[nearestArrayIndex] =
					remaining[
						remaining.length - 1
					]
				remaining.pop()
			}
		} else {
			route = [
				selectedPointIndex,

				...neighborIndexes.sort(
					(a, b) => {
						const aOffset = a * 3
						const bOffset = b * 3
						const adx =
							baseOriginalPositions[aOffset] - originalX
						const ady =
							baseOriginalPositions[aOffset + 1] - originalY
						const adz =
							baseOriginalPositions[aOffset + 2] - originalZ
						const bdx =
							baseOriginalPositions[bOffset] - originalX
						const bdy =
							baseOriginalPositions[bOffset + 1] - originalY
						const bdz =
							baseOriginalPositions[bOffset + 2] - originalZ

						return (
							adx * adx + ady * ady + adz * adz -
							(
								bdx * bdx + bdy * bdy + bdz * bdz
							)
						)
					},
				),
			]
		}

		for (
			let i = 1;
			i < route.length;
			i++
		) {
			const startOffset =
				route[i - 1] * 3
			const endOffset =
				route[i] * 3

			linePositions[writeOffset] = basePositions[startOffset]
			linePositions[writeOffset + 1] = basePositions[startOffset + 1]
			linePositions[writeOffset + 2] = basePositions[startOffset + 2]
			linePositions[writeOffset + 3] = basePositions[endOffset]
			linePositions[writeOffset + 4] = basePositions[endOffset + 1]
			linePositions[writeOffset + 5] = basePositions[endOffset + 2]
			writeOffset += 6
		}
	} else {
		for (
			const neighborIndex of neighborIndexes
		) {
			const offset =
				neighborIndex * 3

			linePositions[writeOffset] = basePositions[selectedOffset]
			linePositions[writeOffset + 1] = basePositions[selectedOffset + 1]
			linePositions[writeOffset + 2] = basePositions[selectedOffset + 2]
			linePositions[writeOffset + 3] = basePositions[offset]
			linePositions[writeOffset + 4] = basePositions[offset + 1]
			linePositions[writeOffset + 5] = basePositions[offset + 2]
			writeOffset += 6
		}
	}

	const lineGeometry =
		new LineSegmentsGeometry()

	lineGeometry.setPositions(
		linePositions,
	)

	const lineMaterial =
		new LineMaterial({
			color: 0xffffff,
			linewidth: 2,
			transparent: true,
			opacity: 0.38,
			depthWrite: false,
		})

	lineMaterial.resolution.set(
		renderer.domElement.clientWidth,
		renderer.domElement.clientHeight,
	)

	relationLines =
		new LineSegments2(
			lineGeometry,
			lineMaterial,
		)

	relationLines.frustumCulled =
		false

	scene.add(
		relationLines,
	)
}

function getPointColorInfo(
	pointIndex,
) {
	const offset =
		pointIndex * 3
	const color =
		new THREE.Color(
			baseColors[offset],
			baseColors[offset + 1],
			baseColors[offset + 2],
		)

	color.convertLinearToSRGB()

	const r =
		THREE.MathUtils.clamp(
			color.r,
			0,
			1,
		)
	const g =
		THREE.MathUtils.clamp(
			color.g,
			0,
			1,
		)
	const b =
		THREE.MathUtils.clamp(
			color.b,
			0,
			1,
		)
	const red = Math.round(r * 255)
	const green = Math.round(g * 255)
	const blue = Math.round(b * 255)
	const hex =
		`#${[
			red,
			green,
			blue,
		].map(
			(value) =>
				value
					.toString(16)
					.padStart(2, '0'),
		).join('')}`

	if (
		color_space.value ===
			'rgb'
	) {
		return {
			space: 'RGB',
			values:
				`R ${red} · G ${green} · B ${blue}`,
			hex,
		}
	}

	if (
		color_space.value ===
			'hsl'
	) {
		const hsl =
			rgbToHsl(
				r,
				g,
				b,
			)

		return {
			space: 'HSL',
			values:
				`H ${Math.round(hsl.h * 360)}° · S ${Math.round(hsl.s * 100)}% · L ${Math.round(hsl.l * 100)}%`,
			hex,
		}
	}

	const hsv =
		rgbToHsv(
			r,
			g,
			b,
		)

	return {
		space: 'HSV',
		values:
			`H ${Math.round(hsv.h * 360)}° · S ${Math.round(hsv.s * 100)}% · V ${Math.round(hsv.v * 100)}%`,
		hex,
	}
}

function selectRenderedPoint(
	renderedIndex,
) {
	const sourceIndex =
		sortOrder[
			renderedIndex
		]

	if (
		!Number.isInteger(
			sourceIndex,
		)
	) {
		return
	}

	selectSourcePoint(
		sourceIndex,
	)
}

function selectSourcePoint(
	sourceIndex,
) {
	if (
		sourceIndex < 0 ||
		sourceIndex * 3 >=
			basePositions.length
	) {
		return
	}

	selectedPointIndex =
		sourceIndex
	selectedPointInfo.value =
		getPointColorInfo(
			sourceIndex,
		)
	copiedPointHex.value = false
	updateOrbitSelectedButton()

	rebuildRelationLines()
}

function updateOrbitSelectedButton() {
	if (
		orbitSelectedButton
	) {
		orbitSelectedButton.disabled =
			selectedPointIndex < 0 ||
			flightActive.value
	}
}

function orbitSelectedPoint() {
	if (
		selectedPointIndex < 0 ||
		!basePositions ||
		!camera ||
		!controls
	) {
		return
	}

	const offset =
		selectedPointIndex * 3
	const target =
		new THREE.Vector3(
			basePositions[offset],
			basePositions[offset + 1],
			basePositions[offset + 2],
		)
	const targetOffset =
		target.clone()
			.sub(
				controls.target,
			)

	camera.position.add(
		targetOffset,
	)
	controls.target.copy(
		target,
	)
	controls.update()

	sortNeeded = true
	saveCameraState()
	saveSettings()
}

function restoreSelectedPoint(
	selectedColor,
) {
	if (
		!selectedColor ||
		!baseColors ||
		baseColors.length === 0
	) {
		clearPointSelection()
		return
	}

	let nearestIndex = 0
	let nearestColorDistanceSquared =
		Infinity
	let nearestOriginalDistanceSquared =
		Infinity

	for (
		let offset = 0;
		offset < baseColors.length;
		offset += 3
	) {
		const dr =
			baseColors[offset] -
			selectedColor.r
		const dg =
			baseColors[offset + 1] -
			selectedColor.g
		const db =
			baseColors[offset + 2] -
			selectedColor.b
		const colorDistanceSquared =
			dr * dr +
			dg * dg +
			db * db
		const dx =
			baseOriginalPositions[offset] -
			selectedColor.x
		const dy =
			baseOriginalPositions[offset + 1] -
			selectedColor.y
		const dz =
			baseOriginalPositions[offset + 2] -
			selectedColor.z
		const originalDistanceSquared =
			dx * dx +
			dy * dy +
			dz * dz

		if (
			colorDistanceSquared <
				nearestColorDistanceSquared -
				0.000000000001 ||
			(
				Math.abs(
					colorDistanceSquared -
					nearestColorDistanceSquared,
				) <= 0.000000000001 &&
				originalDistanceSquared <
					nearestOriginalDistanceSquared
			)
		) {
			nearestColorDistanceSquared =
				colorDistanceSquared
			nearestOriginalDistanceSquared =
				originalDistanceSquared
			nearestIndex =
				offset / 3
		}
	}

	selectSourcePoint(
		nearestIndex,
	)
}

function handlePointPointerDown(
	event,
) {
	if (
		!selection_enabled.value ||
		flightActive.value
	) {
		return
	}

	pointPointerDownX =
		event.clientX
	pointPointerDownY =
		event.clientY
}

function handlePointPointerUp(
	event,
) {
	if (
		!selection_enabled.value ||
		flightActive.value ||
		Math.hypot(
			event.clientX - pointPointerDownX,
			event.clientY - pointPointerDownY,
		) > 5
	) {
		return
	}

	const bounds =
		renderer.domElement
			.getBoundingClientRect()

	pointPointer.x =
		(
			(
				event.clientX - bounds.left
			) / bounds.width
		) * 2 - 1
	pointPointer.y =
		-(
			(
				event.clientY - bounds.top
			) / bounds.height
		) * 2 + 1

	pointRaycaster.params.Points.threshold =
		Math.max(
			0.04,
			dot_size.value * 1.25,
		)
	pointRaycaster.setFromCamera(
		pointPointer,
		camera,
	)


	const intersections =
		pointRaycaster
			.intersectObject(
				dots,
				false,
			)

	intersections.sort(
		(a, b) =>
			(
				a.distanceToRay ??
				Infinity
			) -
			(
				b.distanceToRay ??
				Infinity
			) ||
			a.distance - b.distance,
	)

	const repeatsPreviousPick =
		Math.hypot(
			event.clientX - lastPointPickX,
			event.clientY - lastPointPickY,
		) <= 8

	pointPickCycleIndex =
		repeatsPreviousPick
			? pointPickCycleIndex + 1
			: 0
	lastPointPickX = event.clientX
	lastPointPickY = event.clientY

	const intersection =
		intersections.length > 0
			? intersections[
				pointPickCycleIndex %
				intersections.length
			]
			: null

	if (
		intersection
	) {
		selectRenderedPoint(
			intersection.index,
		)
	} else {
		pointPickCycleIndex = 0
		clearPointSelection()
	}
}

async function copySelectedPointHex() {
	const hex =
		selectedPointInfo.value
			?.hex

	if (
		!hex
	) {
		return
	}

	try {
		await navigator.clipboard.writeText(
			hex,
		)
	} catch {
		const textArea =
			document.createElement(
				'textarea',
			)

		textArea.value = hex
		textArea.style.position =
			'fixed'
		textArea.style.opacity =
			'0'

		document.body.appendChild(
			textArea,
		)
		textArea.select()
		document.execCommand(
			'copy',
		)
		textArea.remove()
	}

	copiedPointHex.value = true
	clearTimeout(
		copiedPointHexTimer,
	)
	copiedPointHexTimer =
		setTimeout(
			() => {
				copiedPointHex.value =
					false
			},
			1200,
		)
}

function updateGeometry() {
	if (
		!dots
	) {
		return
	}

	const selectedColor =
		selectedPointIndex >= 0 &&
		baseColors &&
		baseOriginalPositions
			? {
				r:
					baseColors[
						selectedPointIndex * 3
					],

				g:
					baseColors[
						selectedPointIndex * 3 + 1
					],

				b:
					baseColors[
						selectedPointIndex * 3 + 2
					],

				x:
					baseOriginalPositions[
						selectedPointIndex * 3
					],

				y:
					baseOriginalPositions[
						selectedPointIndex * 3 + 1
					],

				z:
					baseOriginalPositions[
						selectedPointIndex * 3 + 2
					],
			}
			: null

	disposeRelationLines()

	rebuildPaletteData()
	rebuildPaletteOverlay()

	const oldGeometry =
		geometry

	setupGeometry()

	dots.geometry =
		geometry

	if (
		selectedColor
	) {
		restoreSelectedPoint(
			selectedColor,
		)
	}

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
	lastPointPickX = Infinity
	lastPointPickY = Infinity
	pointPickCycleIndex = 0

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

function animate(
	timestamp = performance.now(),
) {
	animationFrame =
		requestAnimationFrame(
			animate,
		)

	const deltaSeconds =
		lastAnimationTime > 0
			? (
				timestamp -
				lastAnimationTime
			) / 1000
			: 1 / 60

	lastAnimationTime = timestamp

	if (
		flightActive.value &&
		flightController
	) {
		const flightState =
			flightController.update(
				deltaSeconds,
			)

		flightRollDegrees.value =
			-flightState.roll *
				180 / Math.PI
		flightPitchOffset.value =
			THREE.MathUtils.clamp(
				flightState.pitch /
					(Math.PI * 0.5) *
					9,
				-9,
				9,
			)

		if (
			camera.isPerspectiveCamera
		) {
			const baseFlightFov =
				Math.max(
					flightViewSettings?.fov ??
						camera_fov.value,
					FLIGHT_TUNING
						.minimumFlightFov,
				)
			const targetFlightFov =
				Math.min(
					baseFlightFov +
						(
							flightState.boosting
								? FLIGHT_TUNING
									.boostFovIncrease
								: 0
						),
					150,
				)

			camera.fov +=
				(
					targetFlightFov -
						camera.fov
				) *
				(
					1 -
						Math.exp(
							-FLIGHT_TUNING
								.fovResponse *
								deltaSeconds,
						)
				)
			camera.updateProjectionMatrix()
		}

		flightFrame += 1

		if (
			flightFrame % 4 === 0
		) {
			flightSpeedDisplay.value =
				flightState.speed
					.toFixed(1)
		}

		if (
			flightFrame % 6 === 0
		) {
			updateFlightProximity()
		}

		if (
			renderMode.value ===
				'splats' &&
			flightFrame % 8 === 0
		) {
			sortNeeded = true
		}
	} else {
		controls.update()
	}

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

function updateDeformationBindingVisibility() {
	if (
		elasticLatticeFolder
	) {
		elasticLatticeFolder.hidden =
			![
				'elastic',
				'combined',
			].includes(
				deformation_mode.value,
			)
	}

	if (
		originalExplosionFolder
	) {
		originalExplosionFolder.hidden =
			![
				'original',
				'combined',
			].includes(
				deformation_mode.value,
			)
	}

	if (
		localCutawayFolder
	) {
		localCutawayFolder.hidden =
			![
				'local',
				'combined',
			].includes(
				deformation_mode.value,
			)
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
		'Color space':
			'Chooses HSV, HSL, or RGB interpolation for both the cloud and palette coordinates.',

		Mode:
			'Chooses between crisp square points and soft Gaussian splats.',

		'Point size':
			'Controls how large each rendered color point appears.',

		'Point density':
			'Sets the grid resolution per axis, so the total point count is density cubed.',

		'Enable selection':
			'Allows points to be selected by clicking or tapping the color cloud.',

		'Relation radius':
			'Chooses neighboring points by their distance from the selected point before deformation.',

		'Line layout':
			'Shows either spokes from the selected point or a nearest-unvisited station route.',

		'Sensitivity':
			'Controls how quickly the mobile flight joystick turns without changing keyboard steering.',

		'Wind volume':
			'Controls the volume of the procedural wind sound while flying.',

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

		'Deform':
			'Enables or disables the selected tunnel deformation on the background cloud.',

		Algorithm:
			'Switches between each deformation algorithm or combines all three effects.',

		'Tunnel radius':
			'Sets the radius immediately around the palette curve used by the selected algorithm.',

		'Explosion width':
			'Sets the narrow band outside the empty tube where local cutaway points are pushed.',

		'Explosion strength':
			'Controls how far points in the local cutaway explosion band move outward.',

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

function beginFineSliderScrub(
	binding,
	track,
	startX,
	startY,
	registerMove,
	registerEnd,
) {
	activeFineSliderFinish?.()

	const minimum = binding.min
	const maximum = binding.max
	const width = Math.max(
		track.getBoundingClientRect().width,
		1,
	)
	let lastX = startX
	let preciseValue =
		binding.controller.value.rawValue
	let finished = false

	const move =
		(clientX, clientY) => {
			const verticalDistance =
				Math.abs(
					clientY - startY,
				)
			const sensitivity =
				Math.max(
					0.0001,
					Math.pow(
						0.1,
						verticalDistance / 100,
					),
				)
			const deltaX =
				clientX - lastX

			preciseValue +=
				deltaX /
				width *
				(
					maximum - minimum
				) *
				sensitivity
			preciseValue =
				THREE.MathUtils.clamp(
					preciseValue,
					minimum,
					maximum,
				)
			lastX = clientX

			binding.controller.value
				.setRawValue(
					preciseValue,
					{
						forceEmit: false,
						last: false,
					},
				)
		}

	const finish =
		() => {
			if (
				finished
			) {
				return
			}

			finished = true
			registerMove(
				null,
			)
			registerEnd(
				null,
			)

			binding.controller.value
				.setRawValue(
					preciseValue,
					{
						forceEmit: true,
						last: true,
					},
				)

			if (
				activeFineSliderFinish ===
				finish
			) {
				activeFineSliderFinish =
					null
			}
		}

	activeFineSliderFinish = finish
	registerMove(
		move,
	)
	registerEnd(
		finish,
	)
}

function setupFineSliderBinding(
	binding,
) {
	const track =
		binding.element.querySelector(
			'.tp-sldv_t',
		)

	if (
		!track ||
		track.dataset.fineScrub ===
			'true' ||
		!Number.isFinite(
			binding.min,
		) ||
		!Number.isFinite(
			binding.max,
		)
	) {
		return
	}

	track.dataset.fineScrub =
		'true'

	let activePointerId = null

	const handlePointerDown =
		(event) => {
			if (
				!event.isPrimary ||
				(
					event.pointerType ===
						'mouse' &&
					event.button !== 0
				)
			) {
				return
			}

			event.preventDefault()
			event.stopImmediatePropagation()
			track.focus()

			activePointerId =
				event.pointerId

			try {
				track.setPointerCapture(
					event.pointerId,
				)
			} catch {
				// Document listeners still keep the scrub active.
			}

			let pointerMove = null
			let pointerEnd = null

			beginFineSliderScrub(
				binding,
				track,
				event.clientX,
				event.clientY,
				(handler) => {
					if (
						pointerMove
					) {
						document.removeEventListener(
							'pointermove',
							pointerMove,
							true,
						)
					}

					pointerMove = handler
						? (moveEvent) => {
							if (
								moveEvent.pointerId !==
									activePointerId
							) {
								return
							}

							moveEvent.preventDefault()
							moveEvent.stopImmediatePropagation()
							handler(
								moveEvent.clientX,
								moveEvent.clientY,
							)
						}
						: null

					if (
						pointerMove
					) {
						document.addEventListener(
							'pointermove',
							pointerMove,
							{
								capture: true,
								passive: false,
							},
						)
					}
				},
				(handler) => {
					if (
						pointerEnd
					) {
						document.removeEventListener(
							'pointerup',
							pointerEnd,
							true,
						)
						document.removeEventListener(
							'pointercancel',
							pointerEnd,
							true,
						)
					}

					pointerEnd = handler
						? (endEvent) => {
							if (
								endEvent.pointerId !==
									activePointerId
							) {
								return
							}

							const pointerId =
								activePointerId

							activePointerId = null

							if (
								pointerId !== null &&
								track.hasPointerCapture(
									pointerId,
								)
							) {
								track.releasePointerCapture(
									pointerId,
								)
							}

							handler()
						}
						: null

					if (
						!handler &&
						activePointerId !== null
					) {
						if (
							track.hasPointerCapture(
								activePointerId,
							)
						) {
							track.releasePointerCapture(
								activePointerId,
							)
						}

						activePointerId = null
					}

					if (
						pointerEnd
					) {
						document.addEventListener(
							'pointerup',
							pointerEnd,
							true,
						)
						document.addEventListener(
							'pointercancel',
							pointerEnd,
							true,
						)
					}
				},
			)
		}

	const handleMouseDown =
		(event) => {
			if (
				activePointerId !== null
			) {
				event.preventDefault()
				event.stopImmediatePropagation()
				return
			}

			if (
				event.button !== 0
			) {
				return
			}

			event.preventDefault()
			event.stopImmediatePropagation()
			track.focus()

			let mouseMove = null
			let mouseUp = null

			beginFineSliderScrub(
				binding,
				track,
				event.clientX,
				event.clientY,
				(handler) => {
					if (
						mouseMove
					) {
						document.removeEventListener(
							'mousemove',
							mouseMove,
							true,
						)
					}

					mouseMove = handler
						? (moveEvent) => {
							moveEvent.preventDefault()
							handler(
								moveEvent.clientX,
								moveEvent.clientY,
							)
						}
						: null

					if (
						mouseMove
					) {
						document.addEventListener(
							'mousemove',
							mouseMove,
							true,
						)
					}
				},
				(handler) => {
					if (
						mouseUp
					) {
						document.removeEventListener(
							'mouseup',
							mouseUp,
							true,
						)
					}

					mouseUp = handler

					if (
						handler
					) {
						document.addEventListener(
							'mouseup',
							handler,
							true,
						)
					}
				},
			)
		}

	const handleTouchStart =
		(event) => {
			if (
				activePointerId !== null
			) {
				event.preventDefault()
				event.stopImmediatePropagation()
				return
			}

			const touch =
				event.changedTouches[0]

			if (
				!touch
			) {
				return
			}

			event.preventDefault()
			event.stopImmediatePropagation()
			track.focus()

			const identifier =
				touch.identifier
			let touchMove = null
			let touchEnd = null

			const findActiveTouch =
				(touches) => {
					for (
						let index = 0;
						index < touches.length;
						index += 1
					) {
						const activeTouch =
							touches.item(index)

						if (
							activeTouch?.identifier ===
								identifier
						) {
							return activeTouch
						}
					}

					return null
				}

			beginFineSliderScrub(
				binding,
				track,
				touch.clientX,
				touch.clientY,
				(handler) => {
					if (
						touchMove
					) {
						document.removeEventListener(
							'touchmove',
							touchMove,
							true,
						)
					}

					touchMove = handler
						? (moveEvent) => {
							const activeTouch =
								findActiveTouch(
									moveEvent.touches,
								)

							if (
								activeTouch
							) {
								moveEvent.preventDefault()
								handler(
									activeTouch.clientX,
									activeTouch.clientY,
								)
							}
						}
						: null

					if (
						touchMove
					) {
						document.addEventListener(
							'touchmove',
							touchMove,
							{
								capture: true,
								passive: false,
							},
						)
					}
				},
				(handler) => {
					if (
						touchEnd
					) {
						document.removeEventListener(
							'touchend',
							touchEnd,
							true,
						)
						document.removeEventListener(
							'touchcancel',
							touchEnd,
							true,
						)
					}

					touchEnd = handler

					if (
						touchEnd
					) {
						document.addEventListener(
							'touchend',
							touchEnd,
							true,
						)
						document.addEventListener(
							'touchcancel',
							touchEnd,
							true,
						)
					}
				},
			)
		}

	const blockLegacyTouchMove =
		(event) => {
			if (
				activePointerId === null
			) {
				return
			}

			event.preventDefault()
			event.stopImmediatePropagation()
		}

	track.addEventListener(
		'pointerdown',
		handlePointerDown,
		{
			capture: true,
			passive: false,
		},
	)

	track.addEventListener(
		'mousedown',
		handleMouseDown,
		true,
	)

	track.addEventListener(
		'touchstart',
		handleTouchStart,
		{
			capture: true,
			passive: false,
		},
	)

	track.addEventListener(
		'touchmove',
		blockLegacyTouchMove,
		{
			capture: true,
			passive: false,
		},
	)

	fineSliderCleanups.push(
		() => {
			track.removeEventListener(
				'pointerdown',
				handlePointerDown,
				true,
			)
			track.removeEventListener(
				'mousedown',
				handleMouseDown,
				true,
			)
			track.removeEventListener(
				'touchstart',
				handleTouchStart,
				true,
			)
			track.removeEventListener(
				'touchmove',
				blockLegacyTouchMove,
				true,
			)
		},
	)
}

function setupFineSliderScrubbing(
	container,
) {
	for (
		const child of
		container.children ?? []
	) {
		setupFineSliderBinding(
			child,
		)

		if (
			child.children
		) {
			setupFineSliderScrubbing(
				child,
			)
		}
	}
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
			color_space,
			'value',
			{
				label:
					'Color space',

				options: {
					HSV:
						'hsv',

					HSL:
						'hsl',

					RGB:
						'rgb',
				},
			},
		)
		.on(
			'change',
			() => {
				updateGeometry()
			},
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


	// Point inspection

	const inspectionFolder =
		pane.addFolder({
			title:
				'Point inspection',

			expanded:
				getPaneExpanded(
					paneState,
					'inspection',
				),
		})

	trackPaneExpanded(
		'inspection',
		inspectionFolder,
	)

	inspectionFolder
		.addBinding(
			selection_enabled,
			'value',
			{
				label:
					'Enable selection',
			},
		)
		.on(
			'change',
			() => {
				if (
					!selection_enabled.value
				) {
					clearPointSelection()
				}

				saveSettings()
			},
		)

	inspectionFolder
		.addBinding(
			inspection_mode,
			'value',
			{
				label:
					'Line layout',

				options: {
					'Local spokes':
						'spokes',

					'Station route':
						'stations',
				},
			},
		)
		.on(
			'change',
			() => {
				rebuildRelationLines()
				saveSettings()
			},
		)

	inspectionFolder
		.addBinding(
			relation_radius,
			'value',
			{
				label:
					'Relation radius',

				min:
					0.01,

				max:
					3,

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
					rebuildRelationLines()
					saveSettings()
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
					'Deform',
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
			deformation_mode,
			'value',
			{
				label:
					'Algorithm',

				options: {
					'Elastic lattice':
						'elastic',

					'Original explosion':
						'original',

					'Local cutaway':
						'local',

					Combined:
						'combined',
				},
			},
		)
		.on(
			'change',
			() => {
				updateDeformationBindingVisibility()
				updateGeometry()
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
					1,

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


	// Original explosion

	originalExplosionFolder =
		pane.addFolder({
			title:
				'Original explosion',

			expanded:
				getPaneExpanded(
					paneState,
					'originalExplosion',
				),
		})

	trackPaneExpanded(
		'originalExplosion',
		originalExplosionFolder,
	)

	originalExplosionFolder.element
		.style.marginTop = '0'

	originalExplosionFolder
		.addBinding(
			original_tunnel_radius,
			'value',
			{
				label:
					'Tunnel radius',

				min: 0,
				max: 5,
				step: 0.01,
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

	// Local cutaway

	localCutawayFolder =
		pane.addFolder({
			title:
				'Local cutaway',

			expanded:
				getPaneExpanded(
					paneState,
					'localCutaway',
				),
		})

	trackPaneExpanded(
		'localCutaway',
		localCutawayFolder,
	)

	localCutawayFolder.element
		.style.marginTop = '0'

	for (
		const binding of
		[
			localCutawayFolder
				.addBinding(
					local_tunnel_radius,
					'value',
					{
						label:
							'Tunnel radius',
						min: 0,
						max: 5,
						step: 0.01,
					},
				),

			localCutawayFolder
				.addBinding(
					explosion_width,
					'value',
					{
						label:
							'Explosion width',

						min:
							0.01,

						max:
							5,

						step:
							0.01,
					},
				),

			localCutawayFolder
				.addBinding(
					explosion_strength,
					'value',
					{
						label:
							'Explosion strength',

						min:
							0,

						max:
							5,

						step:
							0.01,
					},
				),
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


	// Elastic lattice

	elasticLatticeFolder =
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
		elasticLatticeFolder,
	)

	elasticLatticeFolder.element
		.style.marginTop = '0'

	elasticLatticeFolder
		.addBinding(
			tunnel_radius,
			'value',
			{
				label:
					'Tunnel radius',
				min: 0,
				max: 5,
				step: 0.01,
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

	elasticLatticeFolder
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

	elasticLatticeFolder
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

	elasticLatticeFolder
		.addBinding(
			lattice_repulsion_strength,
			'value',
			{
				label:
					'Repulsion',

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

	elasticLatticeFolder
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

	elasticLatticeFolder
		.addBinding(
			lattice_restore_strength,
			'value',
			{
				label:
					'Restore strength',

				min:
					0,

				max:
					12,

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

	updateDeformationBindingVisibility()

	setupSettingDescriptions(
		pane,
	)

	setupFineSliderScrubbing(
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

	const copyPresetButton =
		presetFolder
		.addButton({
			title:
				'Copy preset',
		})
		.on(
			'click',
			() => {
				copyPresetCode()
			},
		)

	const exportAllButton =
		presetFolder
			.addButton({
				title:
					'Export all',
			})
			.on(
				'click',
				() => {
					exportAllPresets()
				},
			)

	const presetExportRow =
		document.createElement(
			'div',
		)

	presetExportRow.className =
		'preset-export-row'
	copyPresetButton.element.before(
		presetExportRow,
	)
	presetExportRow.append(
		copyPresetButton.element,
		exportAllButton.element,
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

	orbitSelectedButton =
		cameraFolder
			.addButton({
				title:
					'Orbit selected',
			})
			.on(
				'click',
				() => {
					orbitSelectedPoint()
				},
			)

	flyButton =
		cameraFolder
			.addButton({
				title:
					'Fly',
			})
			.on(
				'click',
				() => {
					toggleFlight()
				},
			)

	cameraFolder
		.addBinding(
			flight_sensitivity,
			'value',
			{
				label:
					'Sensitivity',
				min:
					0.1,
				max:
					2,
				step:
					0.05,
			},
		)

	cameraFolder
		.addBinding(
			flight_wind_volume,
			'value',
			{
				label:
					'Wind volume',
				min:
					0,
				max:
					1,
				step:
					0.01,
			},
		)
		.on(
			'change',
			() => {
				flightController
					?.setWindVolume(
						flight_wind_volume.value,
					)
				saveSettings()
			},
		)
		.on(
			'change',
			() => {
				flightController
					?.setJoystickSensitivity(
						flight_sensitivity.value,
					)
				saveSettings()
			},
		)

	updateOrbitSelectedButton()
	updateFlyButton()

	updateCameraBindingVisibility()

	setupSettingDescriptions(
		utilityPane,
	)

	setupFineSliderScrubbing(
		utilityPane,
	)
}


// Vue lifecycle

onMounted(() => {
	document.documentElement
		.classList.add(
			'color-explorer-active',
		)

	loadSettings()
	loadPresetFromUrl()
	refreshPresetEntries()

	setupScene()
	const initialCameraState =
		setupCamera()
	setupRenderer()

	setupPalette()
	setupGeometry()
	setupPoints()

	setupControls(
		initialCameraState,
	)
	saveCameraState()
	saveSettings()
	flightController =
		new ColorExplorerFlightController({
			camera,
			onExit: () => {
				stopFlight()
			},
		})
	flightController.setWindVolume(
		flight_wind_volume.value,
	)
	setupPane()
	setupUtilityPane()

	window.addEventListener(
		'resize',
		scheduleCanvasResize,
	)
	setupCanvasResizeTracking()

	startAnimation()
})

onBeforeUnmount(() => {
	saveSettings()

	window.removeEventListener(
		'resize',
		scheduleCanvasResize,
	)

	window.visualViewport
		?.removeEventListener(
			'resize',
			scheduleCanvasResize,
		)

	canvasResizeObserver
		?.disconnect()
	canvasResizeObserver = null

	if (
		pendingCanvasResizeFrame !==
		null
	) {
		cancelAnimationFrame(
			pendingCanvasResizeFrame,
		)
		pendingCanvasResizeFrame =
			null
	}

	renderer
		?.domElement
		.removeEventListener(
			'pointerdown',
			handlePointPointerDown,
		)

	renderer
		?.domElement
		.removeEventListener(
			'pointerup',
			handlePointPointerUp,
		)

	clearTimeout(
		copiedPointHexTimer,
	)

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

	activeFineSliderFinish?.()
	activeFineSliderFinish = null

	for (
		const cleanup of
		fineSliderCleanups
	) {
		cleanup()
	}

	fineSliderCleanups = []

	cancelAnimationFrame(
		animationFrame,
	)

	document.documentElement
		.classList.remove(
			'color-explorer-flight-active',
		)
	document.documentElement
		.classList.remove(
			'color-explorer-active',
		)

	flightController
		?.dispose()
	flightController = null

	controls
		?.dispose()

	pane
		?.dispose()

	utilityPane
		?.dispose()

	disposeRelationLines()

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
	<button
		v-if="!flightActive"
		type="button"
		class="mobile-panel-toggle mobile-settings-toggle"
		:class="{ active: mobilePanel === 'settings' }"
		:aria-expanded="mobilePanel === 'settings'"
		aria-controls="color-explorer-settings"
		@click="toggleMobilePanel('settings')"
	>
		{{ mobilePanel === 'settings' ? 'Close' : 'Settings' }}
	</button>

	<button
		v-if="!flightActive"
		type="button"
		class="mobile-panel-toggle mobile-utility-toggle"
		:class="{ active: mobilePanel === 'utility' }"
		:aria-expanded="mobilePanel === 'utility'"
		aria-controls="color-explorer-utility"
		@click="toggleMobilePanel('utility')"
	>
		{{ mobilePanel === 'utility' ? 'Close' : 'Info & presets' }}
	</button>

	<div
		v-if="mobilePanel"
		class="mobile-panel-backdrop"
		@click="closeMobilePanels"
	></div>

	<div
		v-if="flightActive"
		class="flight-hud"
	>
		<div class="flight-status-group">
			<div class="flight-status">
				<span>Gliding</span>
				<strong>{{ flightSpeedDisplay }}</strong>
				<small>units/s</small>
			</div>

			<svg
				class="flight-roll-indicator"
				viewBox="0 0 90 18"
				role="img"
				aria-label="Aircraft roll relative to the horizon"
			>
				<g :transform="`translate(0 ${flightPitchOffset})`">
					<line
						class="flight-roll-horizon"
						x1="8"
						y1="11"
						x2="82"
						y2="11"
						:transform="`rotate(${flightRollDegrees} 45 11)`"
					></line>
				</g>

				<path
					class="flight-roll-reference"
					d="M39 3 L45 9 L51 3"
				></path>
			</svg>
		</div>

		<button
			type="button"
			class="flight-exit-button"
			@click="stopFlight()"
		>
			Exit flight
		</button>

		<div class="flight-keyboard-help">
			WASD / arrows to steer · Space to boost · Esc to exit
		</div>

		<div
			class="flight-joystick"
			aria-label="Flight steering joystick"
			@pointerdown="handleFlightJoystickDown"
			@pointermove="handleFlightJoystickMove"
			@pointerup="handleFlightJoystickUp"
			@pointercancel="handleFlightJoystickUp"
		>
			<div
				class="flight-joystick-knob"
				:style="{
					left: `${50 + flightJoystick.x * 31.5}%`,
					top: `${50 + flightJoystick.y * 31.5}%`,
				}"
			></div>
		</div>

		<button
			type="button"
			class="flight-boost-button"
			@pointerdown="handleFlightBoost($event, true)"
			@pointerup="handleFlightBoost($event, false)"
			@pointercancel="handleFlightBoost($event, false)"
			@touchstart.stop.prevent="handleFlightBoostTouch(true)"
			@touchend.stop.prevent="handleFlightBoostTouch(false)"
			@touchcancel.stop.prevent="handleFlightBoostTouch(false)"
		>
			Boost
		</button>
	</div>

	<div
		id="color-explorer-settings"
		ref="paneContainer"
		class="pane-container"
		:class="{ 'mobile-open': mobilePanel === 'settings' }"
	></div>

	<div
		id="color-explorer-utility"
		class="utility-container"
		:class="{ 'mobile-open': mobilePanel === 'utility' }"
	>
		<div class="info-panel">
			<div class="point-count">
				<span>Spawned points</span>

				<strong>
					{{ pointCountDisplay }}
				</strong>
			</div>

			<div
				v-if="selectedPointInfo"
				class="selected-point-info"
			>
				<div class="selected-point-heading">
					<span>Selected point</span>

					<strong>{{ selectedPointInfo.space }}</strong>
				</div>

				<div class="selected-point-values">
					{{ selectedPointInfo.values }}
				</div>

				<button
					type="button"
					class="point-hex-button"
					:title="`Copy ${selectedPointInfo.hex}`"
					@click="copySelectedPointHex"
				>
					<span
						class="selected-color-swatch"
						:style="{ backgroundColor: selectedPointInfo.hex }"
					></span>

					<span>
						{{ copiedPointHex ? 'Copied!' : selectedPointInfo.hex }}
					</span>
				</button>

				<small class="selection-cycle-hint">
					Tap the same spot again to cycle through overlapping points.
				</small>
			</div>

			<p v-else>{{ settingHelp }}</p>
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

		<button
			v-if="flightActive"
			type="button"
			class="flight-exit-button-ipad"
			@click="stopFlight()"
		>
			Exit flight
		</button>
	</div>

	<button
		v-if="selectedPointInfo"
		:key="`${selectedPointInfo.hex}:${selectedPointInfo.values}`"
		type="button"
		class="mobile-selected-color"
		:title="`Copy ${selectedPointInfo.hex}`"
		@click="copySelectedPointHex"
	>
		<span
			class="mobile-selected-swatch"
			:style="{ backgroundColor: selectedPointInfo.hex }"
		></span>

		<span class="mobile-selected-details">
			<strong>
				{{ selectedPointInfo.space }} {{ selectedPointInfo.values }}
			</strong>

			<small>
				{{ copiedPointHex ? 'Copied!' : selectedPointInfo.hex }}
			</small>
		</span>
	</button>

	<div
		v-if="presetCodeDialog.open"
		class="confirmation-backdrop"
		role="presentation"
		@click.self="closePresetCode"
	>
		<div
			class="confirmation-dialog preset-export-dialog"
			role="dialog"
			aria-modal="true"
			aria-labelledby="preset-code-title"
			@keydown.esc="closePresetCode"
		>
			<h2 id="preset-code-title">
				{{ presetCodeDialog.title }}
			</h2>

			<p>
				{{ presetCodeDialog.description }}
			</p>

			<textarea
				ref="presetCodeTextarea"
				class="preset-export-textarea preset-code-textarea"
				:readonly="true"
				:value="presetCodeDialog.text"
				:aria-label="presetCodeDialog.ariaLabel"
				@focus="$event.target.select()"
			></textarea>

			<div class="confirmation-actions">
				<button
					type="button"
					@click="closePresetCode"
				>
					Close
				</button>

				<button
					type="button"
					@click="copyCurrentPresetCode"
				>
					{{ presetCodeDialog.copied ? 'Copied!' : presetCodeDialog.copyLabel }}
				</button>
			</div>
		</div>
	</div>

	<div
		v-if="presetExportDialog.open"
		class="confirmation-backdrop"
		role="presentation"
		@click.self="closePresetExport"
	>
		<div
			class="confirmation-dialog preset-export-dialog"
			role="dialog"
			aria-modal="true"
			aria-labelledby="preset-export-title"
			@keydown.esc="closePresetExport"
		>
			<h2 id="preset-export-title">
				Export all named presets
			</h2>

			<p>
				{{ presetExportDialog.count }} local preset{{
					presetExportDialog.count === 1 ? '' : 's'
				}} included. Paste this array into
				<code>DEFAULT_PRESETS</code>.
			</p>

			<textarea
				ref="presetExportTextarea"
				class="preset-export-textarea"
				:readonly="true"
				:value="presetExportDialog.text"
				aria-label="Exported named presets"
				@focus="$event.target.select()"
			></textarea>

			<div class="confirmation-actions">
				<button
					type="button"
					@click="closePresetExport"
				>
					Close
				</button>

				<button
					type="button"
					@click="copyAllPresetExport"
				>
					{{ presetExportDialog.copied ? 'Copied all!' : 'Copy all' }}
				</button>
			</div>
		</div>
	</div>

	<div
		v-if="presetImportDialog.open"
		class="confirmation-backdrop"
		role="presentation"
		@click.self="closePresetImport"
	>
		<div
			class="confirmation-dialog preset-export-dialog"
			role="dialog"
			aria-modal="true"
			aria-labelledby="preset-import-title"
			@keydown.esc="closePresetImport"
		>
			<h2 id="preset-import-title">
				Import preset
			</h2>

			<p>
				Paste a share URL, bare preset code, or exported
				<code>{ name, code }</code> entry.
			</p>

			<textarea
				v-model="presetImportDialog.text"
				class="preset-export-textarea preset-import-textarea"
				autofocus
				aria-label="Preset to import"
				placeholder="Paste preset here…"
			></textarea>

			<p
				v-if="presetImportDialog.error"
				class="preset-import-error"
			>
				{{ presetImportDialog.error }}
			</p>

			<div class="confirmation-actions">
				<button
					type="button"
					@click="closePresetImport"
				>
					Cancel
				</button>

				<button
					type="button"
					@click="submitPresetImport"
				>
					Load preset
				</button>
			</div>
		</div>
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


	<div class="creator-credit">
		v1.
		<br>
		Made by Vena.
	</div>
</template>


<style scoped>
:global(html.color-explorer-active),
:global(html.color-explorer-active body),
:global(html.color-explorer-active #app) {
	width: 100%;
	height: 100%;
	margin: 0;
	overflow: hidden;
}

:global(html.color-explorer-flight-active),
:global(html.color-explorer-flight-active *) {
	-webkit-user-select: none;
	user-select: none;
	-webkit-touch-callout: none;
}

:global(html.color-explorer-flight-active),
:global(html.color-explorer-flight-active body) {
	overscroll-behavior: none;
}

.three-container {
	position: fixed;
	inset: 0;
	overflow: hidden;
}

.three-container :deep(canvas) {
	display: block;
}

.creator-credit {
	position: fixed;
	right: max(10px, env(safe-area-inset-right));
	bottom: max(8px, env(safe-area-inset-bottom));
	z-index: 5;
	color: rgb(129, 129, 129);
	font: 10px/1.2 Roboto Mono, Source Code Pro, Menlo, Courier, monospace;
	pointer-events: none;
	user-select: none;
	text-align: right;
}

.mobile-panel-toggle,
.mobile-panel-backdrop,
.mobile-selected-color {
	display: none;
}

.flight-hud {
	position: fixed;
	inset: 0;
	z-index: 20;
	pointer-events: none;
	font-family:
		Roboto Mono,
		Source Code Pro,
		Menlo,
		Courier,
		monospace;
}

.flight-status-group {
	position: absolute;
	top: 10px;
	left: 50%;
	display: flex;
	flex-direction: column;
	align-items: center;
	transform: translateX(-50%);
}

.flight-status {
	display: flex;
	box-sizing: border-box;
	height: 30px;
	align-items: baseline;
	gap: 6px;
	padding: 6px 9px;
	border: 1px solid rgb(255 255 255 / 14%);
	border-radius: 6px;
	background: hsl(230deg 7% 13% / 76%);
	box-shadow: 0 2px 8px rgb(0 0 0 / 28%);
	color: hsl(230deg 7% 78%);
	font-size: 10px;
	backdrop-filter: blur(5px);
}

.flight-status strong {
	color: white;
	font-size: 13px;
}

.flight-status small {
	color: hsl(230deg 7% 60%);
	font-size: 8px;
}

.flight-roll-indicator {
	display: block;
	width: 90px;
	height: 18px;
	margin-top: 1px;
	overflow: visible;
	fill: none;
	stroke: rgb(255 255 255 / 82%);
	stroke-linecap: round;
	stroke-linejoin: round;
	stroke-width: 1;
}

.flight-exit-button {
	position: absolute;
	top: 10px;
	left: calc(50% + 80px);
	box-sizing: border-box;
	height: 30px;
	pointer-events: auto;
	padding: 5px 9px;
	border: 1px solid rgb(255 255 255 / 14%);
	border-radius: 6px;
	background: hsl(230deg 7% 17% / 86%);
	color: white;
	font: inherit;
	font-size: 9px;
	cursor: pointer;
	backdrop-filter: blur(5px);
}

.flight-exit-button-ipad {
	display: none;
}

.flight-keyboard-help {
	position: absolute;
	bottom: 12px;
	left: 50%;
	padding: 6px 9px;
	border-radius: 5px;
	background: hsl(230deg 7% 13% / 70%);
	color: hsl(230deg 7% 80%);
	font-size: 9px;
	transform: translateX(-50%);
	backdrop-filter: blur(5px);
}

.flight-joystick,
.flight-boost-button {
	display: none;
}

@media (pointer: coarse) {
	.flight-keyboard-help {
		display: none;
	}

	.flight-joystick {
		position: absolute;
		bottom: calc(20px + env(safe-area-inset-bottom));
		left: max(18px, env(safe-area-inset-left));
		display: grid;
		width: 108px;
		height: 108px;
		place-items: center;
		border: 1px solid rgb(255 255 255 / 20%);
		border-radius: 50%;
		background: hsl(230deg 7% 12% / 36%);
		box-shadow: inset 0 0 18px rgb(0 0 0 / 24%);
		pointer-events: auto;
		touch-action: none;
		-webkit-tap-highlight-color: transparent;
	}

	.flight-joystick::before,
	.flight-joystick::after {
		position: absolute;
		background: rgb(255 255 255 / 12%);
		content: '';
		pointer-events: none;
	}

	.flight-joystick::before {
		width: 1px;
		height: 72%;
	}

	.flight-joystick::after {
		width: 72%;
		height: 1px;
	}

	.flight-joystick-knob {
		position: absolute;
		width: 38px;
		height: 38px;
		border: 1px solid rgb(255 255 255 / 28%);
		border-radius: 50%;
		background: hsl(211deg 55% 50% / 78%);
		box-shadow: 0 3px 8px rgb(0 0 0 / 34%);
		pointer-events: none;
		transform: translate(-50%, -50%);
		will-change: left, top;
	}

	.flight-boost-button {
		position: absolute;
		right: max(22px, env(safe-area-inset-right));
		bottom: calc(34px + env(safe-area-inset-bottom));
		display: block;
		width: 74px;
		height: 74px;
		border: 1px solid rgb(255 255 255 / 24%);
		border-radius: 50%;
		background: hsl(24deg 76% 48% / 78%);
		box-shadow: 0 3px 10px rgb(0 0 0 / 34%);
		color: white;
		font: inherit;
		font-size: 11px;
		font-weight: 700;
		appearance: none;
		-webkit-appearance: none;
		pointer-events: auto;
		touch-action: none;
		-webkit-tap-highlight-color: transparent;
	}

	.flight-boost-button:active {
		background: hsl(30deg 90% 58% / 92%);
		transform: scale(0.95);
	}
}

@media (max-width: 700px),
	(max-height: 500px) and (pointer: coarse) {
	.flight-status-group,
	.flight-exit-button {
		top: calc(8px + env(safe-area-inset-top));
	}

	.flight-exit-button {
		left: auto;
		right: max(8px, env(safe-area-inset-right));
	}
}

@media (min-width: 700px) and (min-height: 600px) and (pointer: coarse) {
	.flight-exit-button {
		display: none;
	}

	.flight-exit-button-ipad {
		display: block;
		box-sizing: border-box;
		width: 100%;
		height: 30px;
		margin-top: 8px;
		padding: 6px 9px;
		border: 1px solid rgb(255 255 255 / 14%);
		border-radius: 6px;
		background: hsl(230deg 7% 17% / 86%);
		color: white;
		font: 10px/1.2 Roboto Mono, Source Code Pro, Menlo, monospace;
		cursor: pointer;
		-webkit-tap-highlight-color: transparent;
	}

	.flight-joystick {
		width: 216px;
		height: 216px;
	}

	.flight-joystick-knob {
		width: 76px;
		height: 76px;
		border-width: 2px;
	}

	.flight-boost-button {
		width: 148px;
		height: 148px;
		font-size: 16px;
	}
}

.pane-container {
	position: fixed;
	top: 10px;
	left: 10px;
	z-index: 10;
	width: 280px;
	max-height: calc(100vh - 20px);
	max-height: calc(100dvh - 20px);
	overflow-x: hidden;
	overflow-y: auto;
	overscroll-behavior: contain;
	scrollbar-width: none;
	-webkit-overflow-scrolling: touch;
	touch-action: pan-y;
}

.utility-container {
	position: fixed;
	top: 10px;
	right: 10px;
	z-index: 10;
	width: 300px;
	max-height: calc(100vh - 20px);
	max-height: calc(100dvh - 20px);
	overflow-x: hidden;
	overflow-y: auto;
	overscroll-behavior: contain;
	scrollbar-width: none;
	-webkit-overflow-scrolling: touch;
	touch-action: pan-y;
}

.pane-container::-webkit-scrollbar,
.utility-container::-webkit-scrollbar {
	display: none;
	width: 0;
	height: 0;
}

.pane-container::after,
.utility-container::after {
	display: block;
	height: 64px;
	content: '';
	pointer-events: none;
}

:deep(.preset-export-row) {
	display: grid;
	grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
	gap: 4px;
}

:deep(.preset-export-row > *) {
	min-width: 0;
}

:deep(.preset-export-row > :first-child) {
	padding-right: 0;
}

:deep(.preset-export-row > :last-child) {
	padding-left: 0;
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

.selected-point-info {
	margin-top: 8px;
	padding-top: 8px;
	border-top: 1px solid rgb(187 188 196 / 15%);
}

.selected-point-heading {
	display: flex;
	justify-content: space-between;
	gap: 12px;
}

.selected-point-heading strong {
	color: white;
}

.selected-point-values {
	margin-top: 7px;
	color: hsl(230deg 7% 88%);
	line-height: 1.4;
}

.point-hex-button {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	margin-top: 7px;
	padding: 2px 7px 2px 2px;
	border: 0;
	border-radius: 3px;
	background: hsl(230deg 7% 28%);
	color: white;
	font: inherit;
	cursor: pointer;
}

.point-hex-button:hover,
.point-hex-button:focus-visible {
	background: hsl(230deg 7% 36%);
}

.selected-color-swatch {
	display: block;
	width: 20px;
	height: 20px;
	flex: 0 0 20px;
	border-radius: 2px;
	box-shadow: inset 0 0 0 1px rgb(255 255 255 / 18%);
}

.selection-cycle-hint {
	display: block;
	margin-top: 7px;
	color: hsl(230deg 7% 55%);
	font-size: 9px;
	line-height: 1.35;
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

.preset-export-dialog {
	width: min(720px, 100%);
}

.preset-export-dialog code {
	color: white;
}

.preset-export-textarea {
	box-sizing: border-box;
	display: block;
	width: 100%;
	height: min(46dvh, 360px);
	margin-bottom: 14px;
	padding: 10px;
	border: 1px solid rgb(255 255 255 / 14%);
	border-radius: 4px;
	outline: none;
	background: hsl(230deg 7% 11%);
	color: hsl(230deg 7% 88%);
	font: 10px/1.45 Roboto Mono, Source Code Pro, Menlo, monospace;
	resize: vertical;
	-webkit-overflow-scrolling: touch;
}

.preset-export-textarea:focus {
	border-color: hsl(211deg 70% 55%);
}

.preset-import-textarea {
	height: min(38dvh, 280px);
}

.preset-code-textarea {
	height: min(32dvh, 220px);
}

.confirmation-dialog .preset-import-error {
	margin: -4px 0 12px;
	color: hsl(5deg 80% 70%);
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

:deep(.tp-sldv_t) {
	cursor: ew-resize;
	touch-action: none !important;
}

@media (max-width: 700px),
	(max-height: 500px) and (pointer: coarse) {
	.mobile-panel-toggle {
		position: fixed;
		top: calc(8px + env(safe-area-inset-top));
		z-index: 13;
		display: inline-flex;
		align-items: center;
		min-height: 32px;
		padding: 6px 10px;
		border: 1px solid rgb(255 255 255 / 14%);
		border-radius: 6px;
		background: hsl(230deg 7% 17% / 94%);
		box-shadow: 0 2px 6px rgb(0 0 0 / 25%);
		color: hsl(230deg 7% 88%);
		font: 11px/1.2 Roboto Mono, Source Code Pro, Menlo, monospace;
		cursor: pointer;
		-webkit-tap-highlight-color: transparent;
	}

	.mobile-panel-toggle.active {
		background: hsl(211deg 55% 38% / 96%);
		color: white;
	}

	.mobile-settings-toggle {
		left: max(8px, env(safe-area-inset-left));
	}

	.mobile-utility-toggle {
		right: max(8px, env(safe-area-inset-right));
	}

	.mobile-panel-backdrop {
		position: fixed;
		inset: 0;
		z-index: 11;
		display: block;
		background: rgb(0 0 0 / 28%);
	}

	.mobile-selected-color {
		position: fixed;
		bottom: calc(10px + env(safe-area-inset-bottom));
		left: 50%;
		z-index: 10;
		display: flex;
		align-items: center;
		gap: 8px;
		max-width: calc(100vw - 24px);
		padding: 7px 11px 7px 7px;
		border: 1px solid rgb(255 255 255 / 16%);
		border-radius: 7px;
		background: hsl(230deg 7% 17% / 94%);
		box-shadow: 0 3px 12px rgb(0 0 0 / 35%);
		color: hsl(230deg 7% 92%);
		font: 10px/1.3 Roboto Mono, Source Code Pro, Menlo, monospace;
		text-align: left;
		transform: translateX(-50%);
		animation: mobile-color-pop 180ms ease-out;
		cursor: pointer;
		-webkit-tap-highlight-color: transparent;
	}

	.mobile-selected-swatch {
		display: block;
		width: 28px;
		height: 28px;
		flex: 0 0 28px;
		border-radius: 4px;
		box-shadow: inset 0 0 0 1px rgb(255 255 255 / 20%);
	}

	.mobile-selected-details {
		display: flex;
		min-width: 0;
		flex-direction: column;
		gap: 1px;
	}

	.mobile-selected-details strong {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.mobile-selected-details small {
		color: hsl(230deg 7% 72%);
		font: inherit;
	}

	.pane-container,
	.utility-container {
		top: calc(48px + env(safe-area-inset-top));
		z-index: 12;
		box-sizing: border-box;
		width: min(320px, calc(100vw - 44px));
		max-height: calc(
			100dvh - 58px - env(safe-area-inset-top) -
				env(safe-area-inset-bottom)
		);
		visibility: hidden;
		pointer-events: none;
		transition:
			transform 180ms ease,
			visibility 180ms;
	}

	.pane-container {
		left: max(8px, env(safe-area-inset-left));
		transform: translateX(calc(-100% - 16px));
	}

	.utility-container {
		right: max(8px, env(safe-area-inset-right));
		transform: translateX(calc(100% + 16px));
	}

	.pane-container.mobile-open,
	.utility-container.mobile-open {
		visibility: visible;
		pointer-events: auto;
		transform: translateX(0);
	}
}

@keyframes mobile-color-pop {
	from {
		opacity: 0;
		transform: translate(-50%, 10px) scale(0.96);
	}

	to {
		opacity: 1;
		transform: translateX(-50%) scale(1);
	}
}

</style>
