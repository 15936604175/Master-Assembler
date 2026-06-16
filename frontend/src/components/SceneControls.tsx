import { useRef, useCallback } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export interface ViewPreset {
  id: string;
  label: string;
  position: [number, number, number];
  target?: [number, number, number];
}

interface SceneControlsProps {
  container: { length: number; width: number; height: number };
  onViewChange?: (preset: string) => void;
}

export function getViewPresets(length: number, width: number, height: number): ViewPreset[] {
  const maxDim = Math.max(length, width, height);
  const dist = maxDim * 1.5;
  const target: [number, number, number] = [length / 2, height / 2, width / 2];

  return [
    {
      id: 'perspective',
      label: '透视',
      position: [dist * 0.7, dist * 0.6, dist * 0.7],
      target,
    },
    {
      id: 'front',
      label: '正视',
      position: [length / 2, height / 2, dist + width / 2],
      target,
    },
    {
      id: 'side',
      label: '侧视',
      position: [dist + length / 2, height / 2, width / 2],
      target,
    },
    {
      id: 'top',
      label: '俯视',
      position: [length / 2, dist + height, width / 2],
      target,
    },
    {
      id: 'back',
      label: '后视',
      position: [length / 2, height / 2, -dist + width / 2],
      target,
    },
  ];
}

interface CameraControllerProps {
  targetPosition?: [number, number, number] | null;
  targetLookAt?: [number, number, number] | null;
  onComplete?: () => void;
}

export function CameraController({
  targetPosition,
  targetLookAt,
  onComplete,
}: CameraControllerProps) {
  const { camera, controls } = useThree() as {
    camera: THREE.PerspectiveCamera;
    controls?: { target: THREE.Vector3; update: () => void };
  };
  const animState = useRef<{
    startPos: THREE.Vector3;
    endPos: THREE.Vector3;
    startTarget: THREE.Vector3;
    endTarget: THREE.Vector3;
    progress: number;
  } | null>(null);

  if (targetPosition && !animState.current) {
    animState.current = {
      startPos: camera.position.clone(),
      endPos: new THREE.Vector3(...targetPosition),
      startTarget: controls?.target?.clone() || new THREE.Vector3(),
      endTarget: targetLookAt
        ? new THREE.Vector3(...targetLookAt)
        : controls?.target?.clone() || new THREE.Vector3(),
      progress: 0,
    };
  }

  useFrame((_, delta) => {
    if (animState.current) {
      animState.current.progress += delta * 2.5;
      const t = Math.min(animState.current.progress, 1);
      const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

      camera.position.lerpVectors(
        animState.current.startPos,
        animState.current.endPos,
        eased
      );

      if (controls) {
        controls.target.lerpVectors(
          animState.current.startTarget,
          animState.current.endTarget,
          eased
        );
        controls.update();
      }

      if (t >= 1) {
        animState.current = null;
        onComplete?.();
      }
    }
  });

  return null;
}

export default function SceneControls({ container }: SceneControlsProps) {
  return null;
}
