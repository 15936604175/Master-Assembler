import { useMemo } from 'react';
import * as THREE from 'three';

interface ContainerMeshProps {
  length: number;
  width: number;
  height: number;
  opacity?: number;
  color?: string;
}

export default function ContainerMesh({
  length,
  width,
  height,
  opacity = 0.15,
  color = '#666666',
}: ContainerMeshProps) {
  const edgeGeometry = useMemo(() => {
    const geometry = new THREE.BoxGeometry(length, height, width);
    return new THREE.EdgesGeometry(geometry);
  }, [length, width, height]);

  const edgeMaterial = useMemo(
    () => new THREE.LineBasicMaterial({ color }),
    [color]
  );

  return (
    <group position={[length / 2, height / 2, width / 2]}>
      <mesh>
        <boxGeometry args={[length, height, width]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={opacity}
          side={THREE.DoubleSide}
        />
      </mesh>
      <lineSegments geometry={edgeGeometry} material={edgeMaterial} />
    </group>
  );
}
