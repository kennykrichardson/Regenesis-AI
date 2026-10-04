import { Canvas, useFrame } from "@react-three/fiber";
import { Sparkles } from "@react-three/drei";
import { useMemo, useRef } from "react";
import type { Points } from "three";
import * as THREE from "three";
import { useReducedMotionPreference } from "../hooks/useReducedMotion";

function StarMesh({ count }: { count: number }) {
  const ref = useRef<Points>(null);

  const positions = useMemo(() => {
    const buffer = new Float32Array(count * 3);

    for (let i = 0; i < count; i += 1) {
      buffer[i * 3] = (Math.random() - 0.5) * 22;
      buffer[i * 3 + 1] = (Math.random() - 0.5) * 13;
      buffer[i * 3 + 2] = (Math.random() - 0.5) * 12;
    }

    return buffer;
  }, [count]);

  useFrame((state) => {
    if (!ref.current) return;

    ref.current.rotation.y = state.clock.elapsedTime * 0.018;
    ref.current.rotation.x =
      Math.sin(state.clock.elapsedTime * 0.12) * 0.025;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>

      <pointsMaterial
        color="#08191a"
        size={0.032}
        transparent
        opacity={0.72}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

export default function ParticleField() {
  const reduced = useReducedMotionPreference();

  return (
    <div className="particle-layer" aria-hidden="true">
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 5.5], fov: 52 }}
        gl={{
          antialias: false,
          alpha: true,
        }}
      >
        <ambientLight intensity={0.55} />

        <StarMesh count={reduced ? 180 : 1100} />

        <Sparkles
          count={reduced ? 35 : 140}
          scale={[13, 8, 6]}
          size={2}
          speed={reduced ? 0.025 : 0.2}
          color="#ffffff"
        />

        <Sparkles
          count={reduced ? 15 : 55}
          scale={[8, 5, 4]}
          size={3}
          speed={reduced ? 0.015 : 0.08}
          color="#ffffff"
        />
      </Canvas>
    </div>
  );
}