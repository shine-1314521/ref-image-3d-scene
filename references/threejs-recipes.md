# 可复制代码配方

每个片段都是自包含的，直接粘进 `assets/starter.html` 对应位置即可。
版本基准：`three@0.160`（模块版 + importmap）。换版本先读 `troubleshooting.md` 的版本差异表。

---

## 1 · 骨架与 importmap

单文件用 CDN 模块版；`file://` 直接打开也能跑，因为 CDN 返回 `Access-Control-Allow-Origin: *`。**代价是必须联网。** 需离线则把 `three.module.js` 与 `examples/jsm/` 落到本地 `vendor/`，把 importmap 换成相对路径。

```html
<script type="importmap">
{
  "imports": {
    "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
    "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
  }
}
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls }    from 'three/addons/controls/OrbitControls.js';
import { EffectComposer }   from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass }       from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass }  from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass }       from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass }       from 'three/addons/postprocessing/OutputPass.js';
import { mergeVertices }    from 'three/addons/utils/BufferGeometryUtils.js';
</script>
```

渲染器初始化顺序不能乱：先 `outputColorSpace`，再 `toneMapping`，最后 `shadowMap`。

```js
const renderer = new THREE.WebGLRenderer({ antialias: !IS_MOBILE, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, IS_MOBILE ? CONFIG.perf.mobilePixelRatioCap : CONFIG.perf.pixelRatioCap));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;          // 只在这里声明一次
renderer.toneMapping = { none: THREE.NoToneMapping, aces: THREE.ACESFilmicToneMapping, linear: THREE.LinearToneMapping }[CONFIG.post.toneMapping];
renderer.toneMappingExposure = CONFIG.post.exposure;
renderer.shadowMap.enabled = CONFIG.light.shadow.enabled;
renderer.shadowMap.type = { Basic: THREE.BasicShadowMap, PCF: THREE.PCFShadowMap, VSM: THREE.VSMShadowMap }[CONFIG.light.shadow.type];
document.body.appendChild(renderer.domElement);
```

---

## 2 · 色阶贴图（gradientMap）

三件必做：`NearestFilter`、`generateMipmaps = false`、`colorSpace = NoColorSpace`。
漏最后一个，颜色会被当 sRGB 再线性化一次，画面整体发灰。

```js
function makeToonRamp(ramp) {
  const data = new Uint8Array(ramp.length * 4);
  ramp.forEach((v, i) => {
    const c = Math.round(Math.min(Math.max(v, 0), 1) * 255);
    data.set([c, c, c, 255], i * 4);
  });
  const tex = new THREE.DataTexture(data, ramp.length, 1, THREE.RGBAFormat);
  tex.minFilter = THREE.NearestFilter;   // 不要线性插值，否则台阶被抹平
  tex.magFilter = THREE.NearestFilter;
  tex.generateMipmaps = false;
  tex.colorSpace = THREE.NoColorSpace;   // 关键：否则被二次转换
  tex.needsUpdate = true;
  return tex;
}

const RAMP = makeToonRamp(CONFIG.toon.ramp);

function toonMaterial(colorHex, opts = {}) {
  return new THREE.MeshToonMaterial({
    color: new THREE.Color(colorHex),
    gradientMap: RAMP,
    ...opts,
  });
}
```

`MeshToonMaterial` 没有 `roughness / metalness`，也没有高光。所谓「塑料感」在这套材质下不会出现——出现即说明场景里混进了 `MeshStandardMaterial` 或环境贴图。

---

## 3 · 描边（Inverted Hull）

两个坑必须一起解决：**硬边几何的顶点法线不连续**（立方体角上描边裂口）、**宽度单位**（世界单位在不同视距下粗细不一）。

```js
// 3.1 为描边准备「光滑法线」几何：删 uv 才能跨 UV 接缝合并顶点
function smoothForOutline(geometry) {
  const g = geometry.clone();
  g.deleteAttribute('uv');          // UV 接缝会阻止合并，删掉
  const merged = mergeVertices(g, 1e-4);
  merged.computeVertexNormals();    // 角点法线被平均，外扩不再裂开
  return merged;
}

// 3.1b 曲线几何（Extrude / Lathe / Tube）专用：径向法线外壳
// 上面的 mergeVertices 方案对曲线几何会让正面与侧面法线在圆角接缝互相抵消，
// 描边裂成一圈锯齿状虚线。改为「顶点相对几何中心」的方向，外扩处处连续。
function smoothForOutlineCurved(geometry) {
  const g = geometry.clone();
  g.deleteAttribute('uv');
  g.computeBoundingSphere();
  const c = g.boundingSphere.center;
  const pos = g.getAttribute('position');
  const nrm = new Float32Array(pos.count * 3);
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.set(pos.getX(i) - c.x, pos.getY(i) - c.y, pos.getZ(i) - c.z);
    if (v.lengthSq() < 1e-10) v.set(0, 1, 0);
    v.normalize();
    nrm[i * 3] = v.x; nrm[i * 3 + 1] = v.y; nrm[i * 3 + 2] = v.z;
  }
  g.setAttribute('normal', new THREE.BufferAttribute(nrm, 3));
  return g;
}
// addOutline 里按几何类型分流：
//   const hull = new THREE.Mesh(
//     mesh.geometry.type.includes('Extrude') || mesh.geometry.type.includes('Lathe') ||
//     mesh.geometry.type.includes('Tube')
//       ? smoothForOutlineCurved(mesh.geometry) : smoothForOutline(mesh.geometry),
//     outlineMaterial);

// 3.2 像素 → 世界单位（每个视距单位）。fov 或视口变化后必须重算
// 用 CSS 像素（innerHeight）而非绘制缓冲高度，这样 DPR 变化不改变视觉粗细
function pxToWorldWidth(px) {
  const tanHalf = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
  return (px * 2 * tanHalf) / innerHeight;
}

const OUTLINE_VERT = /* glsl */`
  uniform float uWidth;      // 已换算成「每单位视距」的世界宽度
  uniform float uFadeStart;
  uniform float uFadeEnd;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vec3 n  = normalize(normalMatrix * normal);
    float dist = max(-mv.z, 0.001);
    // 乘视距 => 屏幕空间近似恒定粗细；再乘衰减让远景变细
    float fade = mix(0.3, 1.0, 1.0 - smoothstep(uFadeStart, uFadeEnd, dist));
    mv.xyz += n * uWidth * dist * fade;
    gl_Position = projectionMatrix * mv;
  }`;

const OUTLINE_FRAG = /* glsl */`
  uniform vec3 uColor;
  void main() {
    gl_FragColor = vec4(uColor, 1.0);
  }`;

const outlineMaterial = new THREE.ShaderMaterial({
  uniforms: {
    uWidth:     { value: 0.0014 },
    uColor:     { value: new THREE.Color(CONFIG.toon.outline.color) }, // Color 已转线性
    uFadeStart: { value: CONFIG.toon.outline.fadeStart },
    uFadeEnd:   { value: CONFIG.toon.outline.fadeEnd },
  },
  vertexShader: OUTLINE_VERT,
  fragmentShader: OUTLINE_FRAG,
  side: THREE.BackSide,
});

// 3.3 挂到物体上：作为子节点，自动跟随位移/旋转/缩放
function addOutline(mesh) {
  if (!CONFIG.toon.outline.enabled) return;
  const hull = new THREE.Mesh(smoothForOutline(mesh.geometry), outlineMaterial);
  hull.castShadow = false;
  hull.receiveShadow = false;
  hull.frustumCulled = false;
  mesh.add(hull);
}

// 3.4 resize 或改 fov 后调用
function syncOutlineWidth() {
  outlineMaterial.uniforms.uWidth.value = pxToWorldWidth(CONFIG.toon.outline.px);
}
```

薄片几何（`PlaneGeometry`、花瓣、旗帜）用 hull 会翻面失效 → 改用 `OutlinePass`，或在材质里 `side: DoubleSide` + 顶点外扩。**别在同一物体上混两种描边。**

---

## 4 · 天空（分段色阶 Shader）

用 `ShaderMaterial` 而非 `scene.background`：纯色背景没有分段感，画面立刻变廉价。ShaderMaterial 默认不含雾代码，因此不会被雾吃掉——这一点要显式注释，避免后人误改。

```js
const SKY_VERT = /* glsl */`
  varying vec3 vDir;
  void main() {
    vDir = normalize(position);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;

const SKY_FRAG = /* glsl */`
  uniform vec3  uTop, uMid, uBottom, uSun;
  uniform float uB1, uB2, uSoft, uNoise;
  uniform vec3  uSunDir;
  uniform float uSunSize, uSunGain;
  varying vec3  vDir;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

  void main() {
    vec3  d = normalize(vDir);
    float h = d.y * 0.5 + 0.5;                       // 0 底 → 1 顶
    vec3  c = mix(uBottom, uMid,    smoothstep(uB1 - uSoft, uB1 + uSoft, h));
    c       = mix(c,       uTop,    smoothstep(uB2 - uSoft, uB2 + uSoft, h));

    float s = smoothstep(uSunSize, uSunSize * 0.55, distance(d, uSunDir));
    c += uSun * s * uSunGain;

    c += (hash(gl_FragCoord.xy) - 0.5) * uNoise;      // 极轻噪点，破带状
    gl_FragColor = vec4(c, 1.0);
  }`;

function buildSky() {
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uTop:     { value: new THREE.Color(CONFIG.palette.skyTop) },
      uMid:     { value: new THREE.Color(CONFIG.palette.skyMid) },
      uBottom:  { value: new THREE.Color(CONFIG.palette.skyBottom) },
      uSun:     { value: new THREE.Color(CONFIG.palette.sun) },
      uB1:      { value: CONFIG.sky.bands[0] },
      uB2:      { value: CONFIG.sky.bands[1] },
      uSoft:    { value: CONFIG.sky.softness },
      uNoise:   { value: CONFIG.sky.noise },
      uSunDir:  { value: new THREE.Vector3(...CONFIG.light.sunDir).normalize() },
      uSunSize: { value: CONFIG.sky.sunDisc.size },
      uSunGain: { value: CONFIG.sky.sunDisc.enabled ? CONFIG.sky.sunDisc.gain : 0 },
    },
    vertexShader: SKY_VERT,
    fragmentShader: SKY_FRAG,
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,          // 显式关掉，防止后续改成内建材质时被雾吞
  });
  const sky = new THREE.Mesh(new THREE.SphereGeometry(CONFIG.sky.radius, 32, 16), mat);
  sky.frustumCulled = false;
  return sky;
}
```

---

## 5 · 后处理链

顺序固定，且 `OutputPass` 只能有一个、必须在最后：它负责线性 → sRGB 的唯一一次转换。

```js
const composer = new EffectComposer(renderer);
composer.setSize(innerWidth, innerHeight);
composer.addPass(new RenderPass(scene, camera));

const bloom = new UnrealBloomPass(
  new THREE.Vector2(innerWidth, innerHeight),
  CONFIG.post.bloom.strength,
  CONFIG.post.bloom.radius,
  CONFIG.post.bloom.threshold,
);
composer.addPass(bloom);

const gradePass = new ShaderPass(GradeShader);
composer.addPass(gradePass);

composer.addPass(new OutputPass());   // 必须最后
```

调色合并了「分离色调 + 饱和 + 对比 + 暗角」，一个 pass 干四件事，省三次全屏采样——移动端能救 15% 帧率。

```js
const GradeShader = {
  uniforms: {
    tDiffuse:        { value: null },
    uSaturation:     { value: CONFIG.post.grade.saturation },
    uContrast:       { value: CONFIG.post.grade.contrast },
    uLift:           { value: CONFIG.post.grade.lift },
    uShadowTint:     { value: new THREE.Color(CONFIG.post.grade.shadowTint) },
    uHighlightTint:  { value: new THREE.Color(CONFIG.post.grade.highlightTint) },
    uTintMix:        { value: CONFIG.post.grade.tintMix },
    uVignette:       { value: CONFIG.post.vignette.amount },
    uVigSoft:        { value: CONFIG.post.vignette.softness },
  },
  vertexShader: /* glsl */`
    varying vec2 vUv;
    void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse;
    uniform float uSaturation, uContrast, uLift, uTintMix, uVignette, uVigSoft;
    uniform vec3  uShadowTint, uHighlightTint;
    varying vec2  vUv;

    void main() {
      vec4 c = texture2D(tDiffuse, vUv);
      vec3 col = c.rgb;
      float l = dot(col, vec3(0.2126, 0.7152, 0.0722));

      // 分离色调：暗部染冷，亮部染暖（在线性空间做，不要转 sRGB）
      vec3 tint = mix(uShadowTint, uHighlightTint, smoothstep(0.0, 0.7, l));
      col = mix(col, col * tint * 1.6, uTintMix);

      col = mix(vec3(l), col, uSaturation);            // 饱和
      col = (col - 0.18) * uContrast + 0.18 + uLift;   // 对比，绕线性中灰

      vec2 p = vUv - 0.5;
      float v = 1.0 - uVignette * smoothstep(0.2, 1.0 - uVigSoft * 0.2, length(p) * 1.42);
      col *= v;

      gl_FragColor = vec4(max(col, 0.0), c.a);         // 不做 gamma，交给 OutputPass
    }`,
};
```

注意 `* 1.6`：`uShadowTint` 是 sRGB 深色，转线性后数值很小，直接相乘会把画面压暗，乘个增益补偿。改 `tintMix` 时同步看整体亮度。

---

## 6 · 粒子

贴图用 Canvas 生成，不用外部图片。`alphaTest` 与 `depthWrite:false` 是防止透明排序穿帮的关键。

```js
function makeParticleTexture(mode) {
  const S = 64, cv = document.createElement('canvas');
  cv.width = cv.height = S;
  const g = cv.getContext('2d');
  if (mode === 'firefly') {
    const rg = g.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
    rg.addColorStop(0, 'rgba(255,255,255,1)');
    rg.addColorStop(0.35, 'rgba(255,255,255,0.7)');
    rg.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = rg; g.fillRect(0, 0, S, S);
  } else {
    g.translate(S / 2, S / 2); g.rotate(-0.4);
    g.fillStyle = '#fff';
    g.beginPath();
    g.ellipse(0, 0, S * 0.30, S * 0.16, 0, 0, Math.PI * 2);
    g.fill();
  }
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;   // 颜色贴图用 sRGB
  return tex;
}

function buildParticles() {
  const cfg = CONFIG.anim.particles;
  const n = IS_MOBILE ? Math.min(cfg.count, 150) : cfg.count;
  const pos = new Float32Array(n * 3);
  const phase = new Float32Array(n);
  const b = cfg.bounds;
  for (let i = 0; i < n; i++) {
    pos[i * 3]     = (Math.random() - 0.5) * b;
    pos[i * 3 + 1] = Math.random() * b * 0.6;
    pos[i * 3 + 2] = (Math.random() - 0.5) * b;
    phase[i] = Math.random() * Math.PI * 2;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.userData.phase = phase;

  const mat = new THREE.PointsMaterial({
    size: cfg.size,
    map: makeParticleTexture(cfg.mode),
    transparent: true,
    opacity: cfg.opacity,
    depthWrite: false,
    alphaTest: 0.02,
    sizeAttenuation: true,
    blending: THREE.NormalBlending,
  });

  const points = new THREE.Points(geo, mat);
  points.frustumCulled = false;
  return points;
}

// 每帧更新：越界回收复用，不要 new 任何对象
function updateParticles(points, dt, t) {
  const cfg = CONFIG.anim.particles;
  const attr = points.geometry.attributes.position;
  const phase = points.geometry.userData.phase;
  const b = cfg.bounds;
  for (let i = 0; i < attr.count; i++) {
    let x = attr.getX(i), y = attr.getY(i), z = attr.getZ(i);
    y -= cfg.fall * dt;
    x += Math.sin(t * 0.6 + phase[i]) * cfg.drift * dt;
    z += Math.cos(t * 0.4 + phase[i]) * cfg.drift * 0.6 * dt;
    if (y < 0) { y = b * 0.6; x = (Math.random() - 0.5) * b; z = (Math.random() - 0.5) * b; }
    attr.setXYZ(i, x, y, z);
  }
  attr.needsUpdate = true;
}
```

---

## 7 · 风摆（onBeforeCompile）

不改材质类型，只在顶点阶段插入位移。`customProgramCacheKey` 必须给，否则会和普通 toon 材质共用编译缓存，导致风摆「时有时无」。

```js
const windShaders = [];

function windify(material, { strength, speed, freq }) {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uTime   = { value: 0 };
    shader.uniforms.uWind   = { value: strength };
    shader.uniforms.uSpeed  = { value: speed };
    shader.uniforms.uFreq   = { value: freq };

    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', `
        #include <common>
        uniform float uTime, uWind, uSpeed, uFreq;`)
      .replace('#include <begin_vertex>', `
        #include <begin_vertex>
        float w = sin(uTime * uSpeed + position.y * uFreq) * 0.6
                + sin(uTime * uSpeed * 0.37 + position.x * uFreq * 0.8) * 0.4;
        float h = smoothstep(0.0, 2.2, position.y);   // 根部锁死
        transformed.x += w * uWind * h;
        transformed.z += w * uWind * 0.6 * h;`);

    windShaders.push(shader);
  };
  material.customProgramCacheKey = () => 'wind-toon';
  return material;
}

// 每帧
for (const s of windShaders) s.uniforms.uTime.value = t;
```

---

## 8 · 量化测帧（Stage 2 门禁的落地）

把「像不像」变成数字。主体**实际网格顶点**的屏幕投影 + 地平线位置，和 Stage 0 的基线对差。

> **2026-11-11 修订**：原实现用 `Box3` 的 8 个角点投影，对第一人称场景是错的。
> 伸向镜头的手/袖子会把近角撑出画面（实测报 `w = 1.049`），为了让它 PASS
> 只好给主体组加 `scale.z = 0.551`，结果钞票被压进桌后、被护手完全挡住 ——
> 占比门禁全 PASS，主体亮绿像素却是 0%。改用逐顶点投影后这个假验收不再成立。
> 这里只测构图，**内容可见性另由 `assets/parity-check.py` 测**，两张表要同时过。

```js
const _v = new THREE.Vector3();

function measureFrame(subject) {
  subject.updateWorldMatrix(true, true);
  let minX = 1, maxX = -1, minY = 1, maxY = -1;
  subject.traverse((o) => {
    if (!o.isMesh || !o.geometry) return;
    if (o.material && o.material.side === THREE.BackSide) return;  // 跳过描边外壳
    const p = o.geometry.getAttribute('position');
    if (!p) return;
    const step = p.count > 3000 ? 3 : 1;                          // 大网格抽样
    for (let i = 0; i < p.count; i += step) {
      _v.fromBufferAttribute(p, i).applyMatrix4(o.matrixWorld).project(camera);
      const sx = (_v.x + 1) / 2;
      const sy = (1 - _v.y) / 2;
      minX = Math.min(minX, sx); maxX = Math.max(maxX, sx);
      minY = Math.min(minY, sy); maxY = Math.max(maxY, sy);
    }
  });

  let horizonY = null;
  const fwd = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
  fwd.y = 0;
  if (fwd.lengthSq() > 1e-6) {
    fwd.normalize();
    const p = camera.position.clone().addScaledVector(fwd, 500);
    p.y = camera.position.y;               // 与眼同高的无穷远点 = 地平线
    p.project(camera);
    horizonY = (1 - p.y) / 2;
  }

  return {
    cx: +((minX + maxX) / 2).toFixed(3),
    cy: +((minY + maxY) / 2).toFixed(3),
    w:  +(maxX - minX).toFixed(3),
    h:  +(maxY - minY).toFixed(3),
    horizonY: horizonY === null ? null : +horizonY.toFixed(3),
  };
}
```

判读：`cx/cy/w/h` 都是 0–1 的画面占比（从左上角算）。与 Stage 0 基线逐项对差，超容差就调相机，别调材质。

---

## 8.5 · 曲线几何配方（手绘卡通参考图必用）

只用 `BoxGeometry` + `CylinderGeometry` 拼出来的场景会落成「积木」，
无论色板多准都不像手绘卡通。下面四段是最小可用集，可整体复制进工具层。

```js
// 圆角矩形轮廓（中心在原点，XY 平面）
function roundRectShape(w, h, r) {
  r = Math.max(0.0005, Math.min(r, w / 2 - 0.0005, h / 2 - 0.0005));
  const s = new THREE.Shape();
  const x = -w / 2 + r, X = w / 2 - r, y = -h / 2 + r, Y = h / 2 - r;
  s.moveTo(x, -h / 2); s.lineTo(X, -h / 2);
  s.quadraticCurveTo(w / 2, -h / 2, w / 2, y); s.lineTo(w / 2, Y);
  s.quadraticCurveTo(w / 2, h / 2, X, h / 2); s.lineTo(x, h / 2);
  s.quadraticCurveTo(-w / 2, h / 2, -w / 2, Y); s.lineTo(-w / 2, y);
  s.quadraticCurveTo(-w / 2, -h / 2, x, -h / 2);
  return s;
}
// 任意 Shape 沿 Z 拉伸成有厚度的圆润体（居中）
function geoExtrude(shape, depth, bevel = 0.006) {
  bevel = Math.min(bevel, depth * 0.30);
  const core = Math.max(depth - 2 * bevel, 0.001);
  const g = new THREE.ExtrudeGeometry(shape, {
    depth: core, bevelEnabled: bevel > 0,
    bevelThickness: bevel, bevelSize: bevel,
    bevelSegments: 2, curveSegments: 12, steps: 1,
  });
  g.translate(0, 0, -core / 2); g.computeVertexNormals();
  return g;
}
const geoRoundedBox = (w, h, d, r) => {
  const bevel = Math.min(r * 0.28, d * 0.16);
  return geoExtrude(roundRectShape(w - 2 * bevel, h - 2 * bevel, r), d, bevel);
};
// 旋转体：桶、灯罩、杯、椅背柱头。profile = [[半径, 高度], ...]
const geoLathe = (profile, seg = 20) =>
  new THREE.LatheGeometry(profile.map(([r, y]) =>
    new THREE.Vector2(Math.max(r, 0.0002), y)), seg);
// 空间曲线管：缆绳、电话线、木纹、金色包边
const geoTube = (points, radius, seg = 28, radial = 6) =>
  new THREE.TubeGeometry(
    new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p))),
    seg, radius, radial, false);
```

三个已实测的陷阱：

| 陷阱 | 症状 | 处方 |
|---|---|---|
| 给 `ExtrudeGeometry` 一条**开放轮廓**想画细边 | 自动闭合并填充成一整片色块，盖住后面的物体（实测黄铜片盖掉整张红色椅背） | 细边用 `geoTube` 沿轮廓走；或构造闭合环形 Shape（外轮廓 + 内孔） |
| 给 `ExtrudeGeometry` 挂 `map` 贴图 | UV 是 XY 世界单位而非 0–1，花纹重复/错乱 | 贴图交给标准 `BoxGeometry` 薄片，圆角只负责侧面体积 |
| 所有物体都换成圆角盒就收工 | 椅背弧线、桶身鼓形、缆绳仍是直的，观感还是硬 | 至少用上 Extrude 自定义轮廓 + Lathe + Tube 三类 |

分层建议：结构面（墙/地/天花板）保留平盒以维持直角；
实体道具默认走圆角盒；轮廓特征走 Shape；轴对称物走 Lathe；线状物走 Tube。
`addOutline` 对曲线几何要改用径向法线（见 3.1b）。

---

## 9 · resize 与自适应降级

三处必须同步改，漏一处就变形或糊：`camera.aspect`、`camera.updateProjectionMatrix()`、`composer.setSize`。

```js
function onResize() {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  composer.setSize(innerWidth, innerHeight);
  bloom.setSize(innerWidth, innerHeight);
  syncOutlineWidth();          // 视口高度变了，描边像素宽度要重算
}
addEventListener('resize', onResize);
```

降级顺序：`pixelRatio → bloom → shadow → outline`，每级观察 2s，只降不升（升回来会震荡）。

```js
const quality = { level: 0, frames: 0, elapsed: 0, fps: 60 };

function tickQuality(dt) {
  if (!CONFIG.perf.adaptive.enabled) return;
  quality.frames++;
  quality.elapsed += dt;
  if (quality.elapsed < CONFIG.perf.adaptive.window) return;

  quality.fps = quality.frames / quality.elapsed;
  quality.frames = 0; quality.elapsed = 0;

  if (quality.fps < CONFIG.perf.adaptive.minFps) {
    quality.level++;
    if (quality.level === 1) renderer.setPixelRatio(1);
    if (quality.level === 2) bloom.enabled = false;
    if (quality.level === 3) renderer.shadowMap.enabled = false;
    if (quality.level === 4 && CONFIG.toon.outline.enabled) {
      scene.traverse((o) => { if (o.material === outlineMaterial) o.visible = false; });
    }
    console.info(`[perf] 降级到 L${quality.level}，实测 ${quality.fps.toFixed(1)}fps`);
  }
}
```

`prefers-reduced-motion`：关自动环绕、粒子、风摆，保留可手动旋转。

```js
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
```
