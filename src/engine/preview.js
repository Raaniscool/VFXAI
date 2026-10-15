import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { sampleComponent } from "../organs/builder.js";

/** Preview adapter only. This is not a Roblox scene/export representation. */
export class Preview {
  constructor(container, onFrame, onError) {
    this.container = container;
    this.onFrame = onFrame;
    this.onError = onError;
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "low-power",
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.domElement.setAttribute(
      "aria-label",
      "Interactive procedural 3D effect preview",
    );
    this.renderer.domElement.setAttribute("role", "img");
    container.append(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(42, 1, 0.1, 200);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.minDistance = 4;
    this.controls.maxDistance = 45;
    this.resetCamera();
    this.grid = new THREE.GridHelper(40, 40, 0x263747, 0x19232f);
    this.grid.position.y = -1.8;
    this.grid.material.transparent = true;
    this.grid.material.opacity = 0.5;
    this.scene.add(this.grid);
    this.root = new THREE.Group();
    this.scene.add(this.root);
    this.entries = [];
    this.time = 0.38;
    this.speed = 1;
    this.playing = true;
    this.loop = true;
    this.duration = 1.5;
    this.loopHold = 0;
    this.last = performance.now();
    this.renderer.domElement.addEventListener(
      "webglcontextlost",
      (this.contextLost = (e) => {
        e.preventDefault();
        this.playing = false;
        this.onError(
          "WebGL context lost. Reload the page to restore the preview.",
        );
      }),
    );
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.resize();
    this.renderer.setAnimationLoop((now) => this.frame(now));
  }
  resize() {
    const { width, height } = this.container.getBoundingClientRect();
    this.camera.aspect = width / Math.max(1, height);
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }
  resetCamera() {
    this.camera.position.set(10, 7, 11);
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }
  clear() {
    this.root.traverse((object) => {
      object.geometry?.dispose();
      if (object.material) object.material.dispose();
    });
    this.root.clear();
    this.entries = [];
  }
  load(built) {
    this.clear();
    this.duration = built.duration;
    this.time = Math.min(0.38, built.duration / 3);
    this.loopHold = 0;
    for (const c of built.components) {
      const group = new THREE.Group();
      group.position.fromArray(c.position);
      const material = () =>
        new THREE.MeshBasicMaterial({
          color: c.color,
          transparent: true,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
        });
      if (c.type === "core") {
        group.add(
          new THREE.Mesh(
            new THREE.SphereGeometry(c.properties.radius, 24, 16),
            material(),
          ),
        );
        const shell = new THREE.Mesh(
          new THREE.SphereGeometry(c.properties.radius * 1.6, 12, 8),
          material(),
        );
        shell.userData.opacityFactor = 0.16;
        group.add(shell);
      }
      if (c.type === "ring") {
        const ring = new THREE.Mesh(
          new THREE.TorusGeometry(1, c.properties.thickness, 8, 64),
          material(),
        );
        ring.rotation.x = Math.PI / 2;
        ring.userData.basePositions =
          ring.geometry.attributes.position.array.slice();
        group.add(ring);
      }
      if (c.type === "lightning") {
        for (const arc of c.geometry) {
          const geo = new THREE.BufferGeometry().setFromPoints(
            arc.map((v) => new THREE.Vector3(...v)),
          );
          group.add(
            new THREE.Line(
              geo,
              new THREE.LineBasicMaterial({
                color: c.color,
                transparent: true,
                depthWrite: false,
                blending: THREE.AdditiveBlending,
              }),
            ),
          );
        }
      }
      if (c.type === "particles") {
        const geo = new THREE.BufferGeometry();
        geo.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(
            new Float32Array(c.properties.count * 3),
            3,
          ),
        );
        const mat = new THREE.ShaderMaterial({
          transparent: true,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
          uniforms: {
            color: { value: new THREE.Color(c.color) },
            opacity: { value: 1 },
            size: { value: c.properties.size },
            pixelScale: { value: 1 },
          },
          vertexShader:
            "uniform float size; uniform float pixelScale; void main(){ vec4 p = modelViewMatrix * vec4(position, 1.0); gl_PointSize = clamp(size * pixelScale / max(0.1, -p.z), 1.0, 64.0); gl_Position = projectionMatrix * p; }",
          fragmentShader:
            "uniform vec3 color; uniform float opacity; void main(){ float d = length(gl_PointCoord - vec2(0.5)); if(d > 0.5) discard; gl_FragColor = vec4(color, opacity * (1.0 - smoothstep(0.12, 0.5, d))); }",
        });
        const points = new THREE.Points(geo, mat);
        points.frustumCulled = false;
        group.add(points);
      }
      this.root.add(group);
      this.entries.push({ c, group });
    }
    this.update();
  }
  seek(time) {
    this.time = Math.max(0, Math.min(this.duration, time));
    this.loopHold = 0;
    this.update();
    this.onFrame(this.time, this.renderer.info.render);
  }
  update() {
    for (const { c, group } of this.entries) {
      const s = sampleComponent(c, this.time);
      group.visible = s.visible;
      group.scale.setScalar(s.scale);
      if (c.type === "ring") {
        // Move the torus major radius without scaling its tube thickness.
        const ring = group.children[0];
        const positions = ring.geometry.attributes.position;
        const base = ring.userData.basePositions;
        for (let i = 0; i < positions.count; i++) {
          const x = base[i * 3],
            y = base[i * 3 + 1],
            z = base[i * 3 + 2];
          const radial = Math.hypot(x, y);
          const factor = (s.radius + radial - 1) / radial;
          positions.setXYZ(i, x * factor, y * factor, z);
        }
        positions.needsUpdate = true;
        // Animated bounds must not use the original unit torus radius.
        ring.frustumCulled = false;
      }
      for (const obj of group.children) {
        if (c.type === "particles") {
          const positions = obj.geometry.attributes.position;
          s.positions.forEach((v, i) => positions.setXYZ(i, ...v));
          positions.needsUpdate = true;
          obj.material.uniforms.opacity.value = s.opacity;
          obj.material.uniforms.pixelScale.value =
            (this.container.clientHeight * this.renderer.getPixelRatio()) /
            (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)));
        } else
          obj.material.opacity = s.opacity * (obj.userData.opacityFactor ?? 1);
      }
    }
  }
  frame(now) {
    const dt = Math.min((now - this.last) / 1000, 0.1);
    this.last = now;
    if (this.playing) {
      if (this.time >= this.duration) {
        if (this.loop) {
          this.loopHold += dt;
          if (this.loopHold >= 0.35) {
            this.time = 0;
            this.loopHold = 0;
          }
        } else this.playing = false;
      } else this.time = Math.min(this.duration, this.time + dt * this.speed);
    }
    this.update();
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this.onFrame(this.time, this.renderer.info.render);
  }
  dispose() {
    this.renderer.setAnimationLoop(null);
    this.resizeObserver.disconnect();
    this.controls.dispose();
    this.clear();
    this.grid.geometry.dispose();
    this.grid.material.dispose();
    this.renderer.domElement.removeEventListener(
      "webglcontextlost",
      this.contextLost,
    );
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
