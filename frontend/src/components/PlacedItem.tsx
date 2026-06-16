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
  itemIndex?: number; // 商品序号（同类商品的第几个）
}

export default function PlacedItem({ 
  placement, 
  color, 
  selected, 
  dimmed, 
  hidden, 
  onClick,
  itemIndex 
}: PlacedItemProps) {
  const [hovered, setHovered] = useState(false);

  if (hidden) return null;

  const opacity = selected ? 1.0 : dimmed ? 0.3 : hovered ? 0.95 : 0.85;
  const emissive = selected ? new THREE.Color(color) : new THREE.Color('#000000');
  const emissiveIntensity = selected ? 0.4 : 0;

  // 计算商品序号标签
  const label = itemIndex !== undefined 
    ? `${placement.item_id} #${itemIndex + 1}` 
    : placement.item_id;

  return (
    <group>
      {/* 实体盒子 */}
      <Box
        position={[
          placement.x + placement.length / 2,
          placement.y + placement.height / 2,
          placement.z + placement.width / 2,
        ]}
        args={[placement.length, placement.height, placement.width]}
        onPointerOver={(e) => { 
          e.stopPropagation(); 
          setHovered(true); 
          document.body.style.cursor = 'pointer'; 
        }}
        onPointerOut={() => { 
          setHovered(false); 
          document.body.style.cursor = 'auto'; 
        }}
        onClick={(e) => { 
          e.stopPropagation(); 
          onClick?.(placement); 
        }}
      >
        <meshStandardMaterial
          color={color}
          opacity={opacity}
          transparent={opacity < 1}
          emissive={emissive}
          emissiveIntensity={emissiveIntensity}
          depthWrite={opacity >= 0.8}
          depthTest={true}
          side={THREE.FrontSide}
          roughness={0.4}
          metalness={0.1}
        />
      </Box>
      
      {/* 线框（仅在选中或悬停时显示） */}
      {(selected || hovered) && (
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
            opacity={selected ? 0.9 : 0.5}
            depthWrite={false}
            depthTest={true}
          />
        </Box>
      )}
      
      {/* 商品标签（始终显示） */}
      <Text
        position={[
          placement.x + placement.length / 2,
          placement.y + placement.height + 20,
          placement.z + placement.width / 2,
        ]}
        fontSize={15}
        color={selected ? '#ff0000' : '#333333'}
        outlineWidth={0.5}
        outlineColor="#ffffff"
        anchorX="center"
        anchorY="bottom"
      >
        {label}
      </Text>
      
      {/* 选中时显示详细信息 */}
      {selected && (
        <Text
          position={[
            placement.x + placement.length / 2,
            placement.y + placement.height + 50,
            placement.z + placement.width / 2,
          ]}
          fontSize={12}
          color="#ff0000"
          outlineWidth={0.3}
          outlineColor="#ffffff"
          anchorX="center"
          anchorY="bottom"
        >
          {`位置: (${Math.round(placement.x)}, ${Math.round(placement.y)}, ${Math.round(placement.z)})`}
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