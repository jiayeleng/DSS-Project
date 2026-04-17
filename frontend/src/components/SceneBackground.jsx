import { useEffect, useRef } from "react";
import * as THREE from "three";

/**
 * Shared Three.js background — dot grid + slow drift.
 * Placeholder: replace the geometry/shader later without touching any screen component.
 */
export default function SceneBackground() {
  const mountRef = useRef(null);

  useEffect(() => {
    const el = mountRef.current;
    const W = el.clientWidth;
    const H = el.clientHeight;

    // ── Renderer ──────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(W, H);
    el.appendChild(renderer.domElement);

    // ── Scene / Camera ────────────────────────────────────────
    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-W / 2, W / 2, H / 2, -H / 2, 0.1, 100);
    camera.position.z = 10;

    // ── Dot grid ──────────────────────────────────────────────
    const SPACING = 56;
    const cols = Math.ceil(W / SPACING) + 2;
    const rows = Math.ceil(H / SPACING) + 2;
    const count = cols * rows;

    const positions = new Float32Array(count * 3);
    const basePositions = new Float32Array(count * 3); // original positions for drift
    const offsets = new Float32Array(count);           // per-dot time offset

    let idx = 0;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const x = (c - cols / 2) * SPACING;
        const y = (r - rows / 2) * SPACING;
        positions[idx * 3]     = x;
        positions[idx * 3 + 1] = y;
        positions[idx * 3 + 2] = 0;
        basePositions[idx * 3]     = x;
        basePositions[idx * 3 + 1] = y;
        offsets[idx] = Math.random() * Math.PI * 2;
        idx++;
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));

    const mat = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 2.2,
      sizeAttenuation: false,
      transparent: true,
      opacity: 0.22,
    });

    const dots = new THREE.Points(geo, mat);
    scene.add(dots);

    // ── Line grid ─────────────────────────────────────────────
    const lineMat = new THREE.LineBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.05,
    });

    const lineGeo = new THREE.BufferGeometry();
    const lineVerts = [];

    // horizontals
    for (let r = 0; r < rows; r++) {
      const y = (r - rows / 2) * SPACING;
      lineVerts.push(-W, y, 0, W, y, 0);
    }
    // verticals
    for (let c = 0; c < cols; c++) {
      const x = (c - cols / 2) * SPACING;
      lineVerts.push(x, -H, 0, x, H, 0);
    }

    lineGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(lineVerts), 3));
    const lineSegments = new THREE.LineSegments(lineGeo, lineMat);
    scene.add(lineSegments);

    // ── Resize ────────────────────────────────────────────────
    function onResize() {
      const w = el.clientWidth;
      const h = el.clientHeight;
      renderer.setSize(w, h);
      camera.left   = -w / 2;
      camera.right  =  w / 2;
      camera.top    =  h / 2;
      camera.bottom = -h / 2;
      camera.updateProjectionMatrix();
    }
    const ro = new ResizeObserver(onResize);
    ro.observe(el);

    // ── Animate ───────────────────────────────────────────────
    let raf;
    const clock = new THREE.Clock();

    function animate() {
      raf = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      // subtle dot drift — each dot pulses in opacity slightly
      // (placeholder: replace with particle sim or shader later)
      const posArr = geo.attributes.position.array;
      for (let i = 0; i < count; i++) {
        const drift = Math.sin(t * 0.4 + offsets[i]) * 1.2;
        posArr[i * 3]     = basePositions[i * 3]     + drift;
        posArr[i * 3 + 1] = basePositions[i * 3 + 1] + drift * 0.5;
      }
      geo.attributes.position.needsUpdate = true;

      renderer.render(scene, camera);
    }
    animate();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.dispose();
      geo.dispose();
      mat.dispose();
      lineMat.dispose();
      lineGeo.dispose();
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={mountRef} className="scene-bg" />;
}
