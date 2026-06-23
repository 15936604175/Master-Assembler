import { useState } from 'react';
import { Box, Edges, Html } from '@react-three/drei';
import * as THREE from 'three';
import type { Placement } from '../types';

interface PlacedItemProps {
  placement: Placement;
  color: string;
  selected?: boolean;
  transparent?: boolean;
  hidden?: boolean;
  onClick?: (placement: Placement) => void;
  onDoubleClick?: (placement: Placement) => void;
  itemIndex?: number; // 商品序号（同类商品的第几个）
  labelVisible?: boolean; // 是否显示编号标签（全局显示标签开关）
  distanceFactor?: number; // Html 标签的缩放因子
}

export default function PlacedItem({
  placement,
  color,
  selected,
  transparent: isTransparent,
  hidden,
  onClick,
  onDoubleClick,
  itemIndex,
  labelVisible = false,
  distanceFactor = 200,
}: PlacedItemProps) {
  const [hovered, setHovered] = useState(false);

  if (hidden) return null;

  // 未选中时其他商品变为半透明以突出选中商品的分布
  const opacity = isTransparent ? 0.1 : 1.0;
  const transparentMat = isTransparent;
  const depthWrite = !isTransparent;
  const renderSide = isTransparent ? THREE.DoubleSide : THREE.FrontSide;

  // 透明度不影响颜色本身，选中商品正常发光
  const baseColor = new THREE.Color(color);
  const emissive = selected
    ? new THREE.Color(color)
    : new THREE.Color('#000000');
  const emissiveIntensity = selected ? 0.4 : 0;

  // 商品编号标签：A-01 形式（A 商品的第 1 个）
  const indexStr =
    itemIndex !== undefined
      ? String(itemIndex + 1).padStart(2, '0')
      : '01';
  const label = `${placement.item_id}-${indexStr}`;

  // 中心坐标
  const cx = placement.x + placement.length / 2;
  const cy = placement.y + placement.height / 2;
  const cz = placement.z + placement.width / 2;

  // 标签根据商品尺寸自适应缩放
  const minDim = Math.min(placement.length, placement.height, placement.width);
  const fontSize = Math.max(6, Math.min(12, minDim * 0.04));

  // 边框颜色：默认深灰，hover 黑色，选中红色，透明时浅灰
  const edgeColor = selected ? '#ff0000' : isTransparent ? '#3E3E42' : hovered ? '#A0A0A0' : '#555555';

  return (
    <group>
      {/* 实体盒子 */}
      <Box
        position={[cx, cy, cz]}
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
        onDoubleClick={(e) => {
          e.stopPropagation();
          onDoubleClick?.(placement);
        }}
      >
        <meshStandardMaterial
          color={baseColor}
          opacity={opacity}
          transparent={transparentMat}
          emissive={emissive}
          emissiveIntensity={emissiveIntensity}
          depthWrite={depthWrite}
          depthTest={true}
          side={renderSide}
          roughness={0.4}
          metalness={0.1}
        />
        {/* 边框线：透明商品使用半透明边框 */}
        <Edges
          threshold={15}
          color={edgeColor}
          transparent={isTransparent}
          opacity={isTransparent ? 0.15 : 1}
        />
      </Box>

      {/* 商品编号标签：悬停显示单个，选中显示全部同类 */}
      <Html
        position={[cx, placement.y + placement.height + fontSize * 0.3, cz]}
        center
        distanceFactor={distanceFactor}
        zIndexRange={[20, 0]}
        style={{ pointerEvents: 'none' }}
      >
        {(labelVisible || hovered) && (
          <div
            style={{
              fontSize: fontSize,
              fontWeight: 500,
              whiteSpace: 'nowrap',
              color: selected ? '#ff4444' : '#ffffff',
              textShadow: '0 0 3px rgba(0,0,0,0.8), 0 0 6px rgba(0,0,0,0.5)',
              fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
              pointerEvents: 'none',
              userSelect: 'none',
            }}
          >
            {label}
          </div>
        )}
      </Html>
    </group>
  );
}

export const COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
  '#F0B27A', '#82E0AA', '#F1948A', '#85929E', '#73C6B6',
];
