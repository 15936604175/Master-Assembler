import { useState } from 'react';
import { Box, Edges, Html } from '@react-three/drei';
import * as THREE from 'three';
import type { Placement } from '../types';

interface PlacedItemProps {
  placement: Placement;
  color: string;
  selected?: boolean;
  dimmed?: boolean;
  hidden?: boolean;
  onClick?: (placement: Placement) => void;
  onDoubleClick?: (placement: Placement) => void;
  itemIndex?: number; // 商品序号（同类商品的第几个）
  labelVisible?: boolean; // 是否显示编号标签（选中同类商品时为 true）
  distanceFactor?: number; // Html 标签的缩放因子
}

export default function PlacedItem({
  placement,
  color,
  selected,
  dimmed,
  hidden,
  onClick,
  onDoubleClick,
  itemIndex,
  labelVisible = false,
  distanceFactor = 200,
}: PlacedItemProps) {
  const [hovered, setHovered] = useState(false);

  if (hidden) return null;

  // 关键修复：dimmed 状态不使用透明度，而是通过颜色变暗来表现
  // 这样所有物体都是不透明的，彻底避免透明排序导致的深度冲突问题
  // （透明物体在旋转时排序不稳定，会导致建模闪烁/消失）
  const opacity = 1.0;
  const transparent = false;

  // dimmed 时将颜色与 emissive 都压暗，模拟"暗淡"效果
  const dimFactor = dimmed ? 0.35 : 1.0;
  const baseColor = new THREE.Color(color).multiplyScalar(dimFactor);
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
  const fontSize = Math.max(8, Math.min(18, minDim * 0.06));

  // 边框颜色：默认深灰，hover 黑色，选中红色
  // 关键：边框不使用透明度，避免旋转时透明线框排序不稳定导致闪烁/消失
  const edgeColor = selected ? '#ff0000' : hovered ? '#000000' : '#1e293b';

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
          transparent={transparent}
          emissive={emissive}
          emissiveIntensity={emissiveIntensity}
          depthWrite={true}
          depthTest={true}
          side={THREE.FrontSide}
          roughness={0.4}
          metalness={0.1}
        />
        {/* 始终显示的边框线，用于区分相邻商品（不透明，避免排序问题） */}
        <Edges
          threshold={15}
          color={edgeColor}
        />
      </Box>

      {/* 商品编号标签（仅在选中同类商品时显示） */}
      {labelVisible && (
        <Html
          position={[cx, placement.y + placement.height + fontSize * 0.3, cz]}
          center
          distanceFactor={distanceFactor}
          zIndexRange={[20, 0]}
          style={{ pointerEvents: 'none' }}
        >
          <div
            style={{
              padding: '1px 4px',
              borderRadius: 3,
              background: selected ? 'rgba(239,68,68,0.92)' : 'rgba(255,255,255,0.92)',
              color: selected ? '#fff' : '#0f172a',
              fontSize: fontSize,
              fontWeight: 600,
              whiteSpace: 'nowrap',
              border: selected ? '1px solid #dc2626' : '1px solid #cbd5e1',
              boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
              fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            }}
          >
            {label}
          </div>
        </Html>
      )}
    </group>
  );
}

export const COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
  '#F0B27A', '#82E0AA', '#F1948A', '#85929E', '#73C6B6',
];
