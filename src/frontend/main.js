import * as THREE from 'three';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { FontLoader } from 'three/addons/loaders/FontLoader.js';
import { TextGeometry } from 'three/addons/geometries/TextGeometry.js';
import fontData from 'three/examples/fonts/helvetiker_regular.typeface.json';

const _d = await fetch('/dimensions').then(r => r.json());
var centerBoxHeight = _d.centerBoxHeight;
var leftBoxWidth = _d.leftBoxWidth;
var rightBoxWidth = _d.rightBoxWidth;
const ALL_BOX_DEPTH = 0.3254;
const CENTER_BOX_WIDTH = 0.4754;
const LEFT_BOX_HEIGHT = 0.1754;
const RIGHT_BOX_HEIGHT = 0.2754;

const TAG_WIDTH = 0.1;
const TAG_HEIGHT = 0.1;
const TAG_DEPTH = 0.001;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer();
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

const centerBoxGeometry = new THREE.BoxGeometry(CENTER_BOX_WIDTH, centerBoxHeight, ALL_BOX_DEPTH);
const centerEdgesGeometry = new THREE.EdgesGeometry(centerBoxGeometry);
const centerLineGeo = new LineSegmentsGeometry().fromEdgesGeometry(centerEdgesGeometry);

const rightBoxGeometry = new THREE.BoxGeometry(rightBoxWidth, RIGHT_BOX_HEIGHT, ALL_BOX_DEPTH);
const rightEdgesGeometry = new THREE.EdgesGeometry(rightBoxGeometry);
const rightLineGeo = new LineSegmentsGeometry().fromEdgesGeometry(rightEdgesGeometry);

const leftBoxGeometry = new THREE.BoxGeometry(leftBoxWidth, LEFT_BOX_HEIGHT, ALL_BOX_DEPTH);
const leftEdgesGeometry = new THREE.EdgesGeometry(leftBoxGeometry);
const leftLineGeo = new LineSegmentsGeometry().fromEdgesGeometry(leftEdgesGeometry);

const material = new LineMaterial({
  color: 0xffffff,
  linewidth: 5,
  resolution: new THREE.Vector2(window.innerWidth, window.innerHeight),
});

const tagGeometry = new THREE.BoxGeometry( TAG_WIDTH, TAG_HEIGHT, TAG_DEPTH );
const tagMaterial = new THREE.MeshBasicMaterial( { color: 0xf987c5 } );

const tagFrontLeft = new THREE.Mesh( tagGeometry, tagMaterial );
const tagFrontTop = new THREE.Mesh( tagGeometry, tagMaterial );
const tagFrontBottom = new THREE.Mesh( tagGeometry, tagMaterial );
const tagFrontRight = new THREE.Mesh( tagGeometry, tagMaterial );
const tagBackLeft = new THREE.Mesh( tagGeometry, tagMaterial );
const tagBackTop = new THREE.Mesh( tagGeometry, tagMaterial );
const tagBackBottom = new THREE.Mesh( tagGeometry, tagMaterial );
const tagBackRight = new THREE.Mesh( tagGeometry, tagMaterial );

scene.add(tagFrontLeft);
scene.add(tagFrontTop);
scene.add(tagFrontBottom);
scene.add(tagFrontRight);
scene.add(tagBackLeft);
scene.add(tagBackTop);
scene.add(tagBackBottom);
scene.add(tagBackRight);

const centerWireframe = new LineSegments2(centerLineGeo, material);
const rightWireframe = new LineSegments2(rightLineGeo, material);
const leftWireframe = new LineSegments2(leftLineGeo, material);
scene.add(centerWireframe);
scene.add(rightWireframe);
scene.add(leftWireframe);

camera.position.z = 2;
camera.rotation.x = -Math.PI/2;

const controls = new OrbitControls( camera, renderer.domElement );
controls.update();

const textLoader = new FontLoader();
const textFont = textLoader.parse(fontData);
const textConfig = {
	font: textFont,
	size: 0.075,
	depth: 0.01,
	curveSegments: 12
}
const textMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff });

const leftDimensionGeometry = new TextGeometry( 'Hello three.js!',  textConfig);
const centerDimensionGeometry = new TextGeometry( 'Hello three.js!',  textConfig);
const rightDimensionGeometry = new TextGeometry( 'Hello three.js!',  textConfig);

const leftDimensionMesh = new THREE.Mesh( leftDimensionGeometry, textMaterial);
const centerDimensionMesh = new THREE.Mesh( centerDimensionGeometry, textMaterial);
const rightDimensionMesh = new THREE.Mesh( rightDimensionGeometry, textMaterial);

function updateDimensionText(mesh, newText) {
  mesh.geometry.dispose();
  const newGeometry = new TextGeometry(newText, textConfig);
  newGeometry.computeBoundingBox();
  newGeometry.center();
  mesh.geometry = newGeometry;
}

updateDimensionText(leftDimensionMesh, `${leftBoxWidth.toFixed(3) * 100}cm`);
updateDimensionText(centerDimensionMesh, `${centerBoxHeight.toFixed(3) * 100}cm`);
updateDimensionText(rightDimensionMesh, `${rightBoxWidth.toFixed(3) * 100}cm`);

scene.add(leftDimensionMesh);
scene.add(rightDimensionMesh);
scene.add(centerDimensionMesh);

renderer.setAnimationLoop(animate);

setInterval(async () => {
  const d = await fetch('/dimensions').then(r => r.json());
  if (d.centerBoxHeight !== centerBoxHeight || d.leftBoxWidth !== leftBoxWidth || d.rightBoxWidth !== rightBoxWidth) {
    centerBoxHeight = d.centerBoxHeight;
    leftBoxWidth = d.leftBoxWidth;
    rightBoxWidth = d.rightBoxWidth;
    updateDimensionText(leftDimensionMesh, `${(leftBoxWidth * 100).toFixed(3)}cm`);
    updateDimensionText(centerDimensionMesh, `${(centerBoxHeight * 100).toFixed(3)}cm`);
    updateDimensionText(rightDimensionMesh, `${(rightBoxWidth * 100).toFixed(3)}cm`);

	
  }
}, 500);

function animate(time) {
	centerWireframe.position.y = centerBoxHeight/2;
	leftWireframe.position.y = LEFT_BOX_HEIGHT/2;
	rightWireframe.position.y = RIGHT_BOX_HEIGHT/2;
	rightWireframe.position.x = CENTER_BOX_WIDTH/2 + rightBoxWidth/2;
	leftWireframe.position.x = -CENTER_BOX_WIDTH/2 - leftBoxWidth/2;

	tagFrontLeft.position.z = -ALL_BOX_DEPTH/2;
	tagFrontTop.position.z = -ALL_BOX_DEPTH/2;
	tagFrontBottom.position.z = -ALL_BOX_DEPTH/2;
	tagFrontRight.position.z = -ALL_BOX_DEPTH/2;
	tagBackLeft.position.z = ALL_BOX_DEPTH/2
	tagBackTop.position.z = ALL_BOX_DEPTH/2
	tagBackBottom.position.z = ALL_BOX_DEPTH/2
	tagBackRight.position.z = ALL_BOX_DEPTH/2

	tagFrontLeft.position.x = -CENTER_BOX_WIDTH/2 - leftBoxWidth + TAG_WIDTH/2;
	tagBackLeft.position.x = -CENTER_BOX_WIDTH/2 - leftBoxWidth + TAG_WIDTH/2;
	tagBackLeft.position.y = LEFT_BOX_HEIGHT - TAG_HEIGHT/2;
	tagFrontLeft.position.y = LEFT_BOX_HEIGHT - TAG_HEIGHT/2;

	tagFrontTop.position.y = centerBoxHeight - TAG_HEIGHT/2;
	tagBackTop.position.y = centerBoxHeight - TAG_HEIGHT/2;
	tagFrontTop.position.x = -CENTER_BOX_WIDTH/2 + TAG_HEIGHT/2;
	tagBackTop.position.x = -CENTER_BOX_WIDTH/2 + TAG_HEIGHT/2;

	tagFrontBottom.position.y = TAG_HEIGHT/2;
	tagBackBottom.position.y = TAG_HEIGHT/2;

	tagFrontRight.position.x = CENTER_BOX_WIDTH/2 + rightBoxWidth - TAG_WIDTH/2;
	tagBackRight.position.x = CENTER_BOX_WIDTH/2 + rightBoxWidth - TAG_WIDTH/2;
	tagFrontRight.position.y = TAG_HEIGHT/2;
	tagBackRight.position.y = TAG_HEIGHT/2;

	centerDimensionMesh.position.y = centerBoxHeight + 0.1;

	leftDimensionMesh.position.y = LEFT_BOX_HEIGHT + 0.1;
	leftDimensionMesh.position.x = -CENTER_BOX_WIDTH/2 - leftBoxWidth/2;	

	rightDimensionMesh.position.y = RIGHT_BOX_HEIGHT + 0.1;
	rightDimensionMesh.position.x = CENTER_BOX_WIDTH/2 + rightBoxWidth/2;

	controls.update();

  	renderer.render(scene, camera);
}
