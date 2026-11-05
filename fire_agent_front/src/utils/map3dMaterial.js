/**
 * 3D 地图（Three.js）· 自定义 shader 材质与资源释放
 *
 * 阶段 4h：从 components/map/Map3D.vue 中整段搬出，逻辑一字未改；
 * 仅把原本闭包内的模块级常量（DEPTH / sweepMat）改为显式入参。
 */
import * as THREE from 'three'

// ====== 侧面扫光 shader（移植 sc-datav ShiftMaterial） ======
export function makeSweepMaterial(depth) {
  return new THREE.ShaderMaterial({
    transparent: true,
    uniforms: {
      time: { value: 0 },
      depth: { value: depth },
      baseTopColor: { value: new THREE.Color('#27506b') },
      baseBottomColor: { value: new THREE.Color('#0d1b2c') },
      scanColor: { value: new THREE.Color('#4cc9f0') },
      opacity: { value: 1.0 },
    },
    vertexShader: `
      varying vec3 vPosition;
      void main() {
        vPosition = position;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: `
      varying vec3 vPosition;
      uniform float time;
      uniform float depth;
      uniform vec3 baseTopColor;
      uniform vec3 baseBottomColor;
      uniform vec3 scanColor;
      uniform float opacity;
      void main() {
        float bandHeight = 0.45;
        float normalizedHeight = clamp(vPosition.z / depth, 0.0, 1.0);
        float progress = fract(time) * (1.0 + bandHeight) - bandHeight;
        float distance = (progress + bandHeight) - normalizedHeight;
        float belowHead = step(0.0, distance);
        float withinBand = clamp(1.0 - distance / bandHeight, 0.0, 1.0) * belowHead;
        float feather = smoothstep(0.0, 1.0, withinBand);
        float bandCore = pow(feather, 1.5);
        float bandEdge = smoothstep(0.0, 0.6, withinBand) * (1.0 - smoothstep(0.6, 1.0, withinBand));
        float scanStrength = (bandCore * 0.85 + bandEdge * 0.4);
        if (normalizedHeight < 0.001 || normalizedHeight > 0.999) {
          scanStrength = 0.0;
        }
        vec3 baseColor = mix(baseBottomColor, baseTopColor, normalizedHeight);
        vec3 scanned = mix(baseColor, scanColor, clamp(scanStrength, 0.0, 1.0));
        gl_FragColor = vec4(scanned, opacity);
      }`,
  })
}

// ====== 上升光柱 shader（移植 sc-datav SparklesImplMaterial） ======
export function makeBeamMaterial(opacity) {
  return new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    uniforms: {
      uColor: { value: new THREE.Color('#7dd3fc') },
      uOpacity: { value: opacity },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: `
      uniform vec3 uColor;
      uniform float uOpacity;
      varying vec2 vUv;
      void main() {
        float strength = 1.0 - abs(vUv.x - 0.5) * 2.0;
        strength = pow(strength, 2.0);
        float verticalFade = sin(vUv.y * 3.14159);
        verticalFade = pow(verticalFade, 0.5);
        float brightness = strength * verticalFade;
        gl_FragColor = vec4(uColor * brightness * 2.0, brightness * uOpacity);
      }`,
  })
}

// 递归释放 group 内的 geometry / material 与 CSS2D 标签 DOM
// sharedMat（共享的 sweepMat）不在此销毁
export function disposeGroup(group, sharedMat) {
  group.traverse(obj => {
    if (obj.geometry) obj.geometry.dispose()
    if (obj.material) {
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material]
      mats.forEach(m => {
        // 共享资源（sweepMat/贴图）不在此销毁
        if (m !== sharedMat) m.dispose()
      })
    }
    if (obj.isCSS2DObject && obj.element && obj.element.parentNode) {
      obj.element.parentNode.removeChild(obj.element)
    }
  })
}
