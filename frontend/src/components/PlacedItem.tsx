import { useState } from 'react';
import { Box, Text } from '@react-three/drei';
import * as THREE from 'three';
import type { Placement } from '../types';

interface PlacedItemProps {
  placement: Placement;
  color: string;
  selected?: boolean;
  dimmed?: boolean;
  hidden?: boolean;
  onClick?: (placement: Placement) => void;
}

export default function PlacedItem({ placement, color, selected, dimmed, hidden, onClick }: PlacedItemProps) {
  const [hovered, setHovered] = useState(false);

  if (hidden) return null;

  const opacity = selected ? 1.0 : dimmed ? 0.15 : 0.85;
  const emissive = selected ? new THREE.Color(color) : new THREE.Color('#000000');
  const emissiveIntensity = selected ? 0.3 : 0;

  return (
    <group>
      <Box
        position={[
          placement.x + placement.length / 2,
          placement.y + placement.height / 2,
          placement.z + placement.width / 2,
        ]}
        args={[placement.length, placement.height, placement.width]}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(true); document.body.style.cursor = 'pointer'; }}
        onPointerOut={() => { setHovered(false); document.body.style.cursor = 'auto'; }}
        onClick={(e) => { e.stopPropagation(); onClick?.(placement); }}
      >
        <meshStandardMaterial
          color={color}
          opacity={opacity}
          transparent
          emissive={emissive}
          emissiveIntensity={emissiveIntensity}
        />
      </Box>
      <Box
        position={[
          placement.x + placement.length / 2,
          placement.y + placement.height / 2,
          placement.z + placement.width / 2,
        ]}
        args={[placement.length, placement.height, placement.width]}
      >
        <meshBasicMaterial
          color={selected ? '#ff0000' : '#000000'}
          wireframe
          transparent
          opacity={selected ? 0.8 : hovered ? 0.4 : 0.08}
        />
      </Box>
      {selected && (
        <Text
          position={[
            placement.x + placement.length / 2,
            placement.y + placement.height + 30,
            placement.z + placement.width / 2,
          ]}
          fontSize={25}
          color="#ff0000"
          outlineWidth={0.1}
          outlineColor="#ffffff"
        >
          {`${placement.item_id} (${Math.round(placement.x)},${Math.round(placement.y)},${Math.round(placement.z)})`}
        </Text>
      )}
    </group>
  );
}

export const COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
  '#F0B27A', '#82E0AA', '#F1948A', '#85929E', '#73C6B6',
];
