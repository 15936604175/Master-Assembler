import { Suspense, useMemo, useState, useRef, useCallback } from 'react';
import { Canvas, useThree, useFrame } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import * as THREE from 'three';
import PlacedItem, { COLORS } from './PlacedItem';
import ContainerMesh from './ContainerMesh';
import { getViewPresets, type ViewPreset } from './SceneControls';
import type { Placement, OptimizeResponse, ContainerConfig } from '../types';

interface Layout3DProps {
  result: OptimizeResponse | null;
  container: ContainerConfig;
}

interface CameraAnimatorProps {
  target: ViewPreset | null;
  onArrived: () => void;
}

function CameraAnimator({ target, onArrived }: CameraAnimatorProps) {
  const { camera, controls } = useThree() as {
    camera: THREE.PerspectiveCamera;
    controls: { target: THREE.Vector3; update: () => void };
  };
  const animRef = useRef<{
    startPos: THREE.Vector3;
    endPos: THREE.Vector3;
    startTarget: THREE.Vector3;
    endTarget: THREE.Vector3;
    progress: number;
  } | null>(null);

  if (target && !animRef.current) {
    animRef.current = {
      startPos: camera.position.clone(),
      endPos: new THREE.Vector3(...target.position),
      startTarget: controls.target.clone(),
      endTarget: target.target
        ? new THREE.Vector3(...target.target)
        : controls.target.clone(),
      progress: 0,
    };
  }

  useFrame((_, delta) => {
    if (animRef.current) {
      animRef.current.progress += delta * 2;
      const t = Math.min(animRef.current.progress, 1);
      const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

      camera.position.lerpVectors(
        animRef.current.startPos,
        animRef.current.endPos,
        eased
      );
      controls.target.lerpVectors(
        animRef.current.startTarget,
        animRef.current.endTarget,
        eased
      );
      controls.update();

      if (t >= 1) {
        animRef.current = null;
        onArrived();
      }
    }
  });

  return null;
}

interface SceneInnerProps {
  result: OptimizeResponse | null;
  container: ContainerConfig;
  selectedId: string | null;
  hiddenIds: Set<string>;
  onSelect: (id: string | null) => void;
  onToggleHide: (id: string) => void;
  cameraTarget: ViewPreset | null;
  onCameraArrived: () => void;
  distanceFactor: number;
}

function SceneInner({
  result,
  container,
  selectedId,
  hiddenIds,
  onSelect,
  onToggleHide,
  cameraTarget,
  onCameraArrived,
  distanceFactor,
}: SceneInnerProps) {
  const itemColors = useMemo(() => {
    const colorMap: Record<string, string> = {};
    if (result) {
      const ids = [...new Set(result.placements.map((p) => p.item_id))];
      ids.forEach((id, i) => {
        colorMap[id] = COLORS[i % COLORS.length];
      });
    }
    return colorMap;
  }, [result]);

  const itemIndices = useMemo(() => {
    if (!result) return new Map<number, number>();
    const indices = new Map<number, number>();
    const counters = new Map<string, number>();
    
    result.placements.forEach((p, i) => {
      const currentCount = counters.get(p.item_id) || 0;
      counters.set(p.item_id, currentCount + 1);
      indices.set(i, currentCount);
    });
    
    return indices;
  }, [result]);

  const handleClick = useCallback(
    (placement: Placement) => {
      onSelect(placement.item_id === selectedId ? null : placement.item_id);
    },
    [selectedId, onSelect]
  );

  const handleDoubleClick = useCallback(
    (placement: Placement) => {
      onToggleHide(placement.item_id);
    },
    [onToggleHide]
  );

  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight
        position={[container.length * 0.5, container.height * 1.5, container.width * 0.5]}
        intensity={0.8}
      />
      <directionalLight
        position={[container.length * 0.5, container.height * 0.5, container.width * 0.5]}
        intensity={0.4}
      />
      <ContainerMesh length={container.length} width={container.width} height={container.height} />
      {result?.placements.map((p, i) => (
        <PlacedItem
          key={i}
          placement={p}
          color={itemColors[p.item_id] || '#888'}
          selected={selectedId === p.item_id}
          dimmed={selectedId !== null && selectedId !== p.item_id}
          hidden={hiddenIds.has(p.item_id)}
          onClick={handleClick}
          onDoubleClick={handleDoubleClick}
          itemIndex={itemIndices.get(i)}
          labelVisible={selectedId !== null && selectedId === p.item_id}
          distanceFactor={distanceFactor}
        />
      ))}
      <Grid
        position={[container.length / 2, 0, container.width / 2]}
        args={[container.length, container.width]}
        cellSize={Math.max(container.length, container.width) / 10}
        cellThickness={0.5}
        cellColor="#cbd5e1"
        sectionSize={Math.max(container.length, container.width) / 2}
        sectionThickness={1}
        sectionColor="#94a3b8"
      />
      <OrbitControls
        makeDefault
        target={[container.length / 2, container.height / 2, container.width / 2]}
        enableDamping={true}
        dampingFactor={0.05}
        rotateSpeed={0.8}
      />
      <CameraAnimator target={cameraTarget} onArrived={onCameraArrived} />
    </>
  );
}

export default function Layout3D({ result, container }: Layout3DProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hiddenIds, setHiddenIds] = useState<Set<string>>(new Set());
  const [cameraTarget, setCameraTarget] = useState<ViewPreset | null>(null);
  const maxDim = Math.max(container.length, container.height, container.width);
  const camDist = maxDim * 1.5;

  // 双击商品切换该类商品隐藏/显示
  const toggleHide = useCallback((id: string) => {
    setHiddenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const viewPresets = useMemo(
    () => getViewPresets(container.length, container.width, container.height),
    [container.length, container.width, container.height]
  );

  const itemIds = useMemo(() => {
    if (!result) return [];
    return [...new Set(result.placements.map((p) => p.item_id))];
  }, [result]);

  const toggleHidden = (id: string) => {
    setHiddenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleViewPreset = (preset: ViewPreset) => {
    setCameraTarget(preset);
  };

  const handleCameraArrived = () => {
    setCameraTarget(null);
  };

  const toolBtnStyle: React.CSSProperties = {
    padding: '6px 12px',
    fontSize: 12,
    border: '1px solid #e2e8f0',
    borderRadius: 6,
    background: '#fff',
    color: '#475569',
    cursor: 'pointer',
    transition: 'all 0.2s',
    fontWeight: 500,
  };

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        minHeight: 400,
        background: '#e2e8f0',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* 3D 视图工具条 */}
      <div style={{
        height: 40,
        background: '#fff',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 12px',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>3D 装配视图</span>
          <span style={{ fontSize: 11, color: '#94a3b8' }}>
            {container.length}×{container.width}×{container.height} mm
          </span>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {viewPresets.map((preset) => (
            <button
              key={preset.id}
              onClick={() => handleViewPreset(preset)}
              style={toolBtnStyle}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#1d4ed8'; e.currentTarget.style.color = '#1d4ed8'; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.color = '#475569'; }}
            >
              {preset.label}
            </button>
          ))}
          <div style={{ width: 1, background: '#e2e8f0', margin: '0 4px' }} />
          <button
            onClick={() => {
              setSelectedId(null);
              setHiddenIds(new Set());
            }}
            style={toolBtnStyle}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#1d4ed8'; e.currentTarget.style.color = '#1d4ed8'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.color = '#475569'; }}
          >
            重置
          </button>
          <button
            onClick={() => {
              if (selectedId) {
                setHiddenIds(new Set(itemIds.filter((id) => id !== selectedId)));
              }
            }}
            style={{
              ...toolBtnStyle,
              background: selectedId ? '#eff6ff' : '#fff',
              borderColor: selectedId ? '#1d4ed8' : '#e2e8f0',
              color: selectedId ? '#1d4ed8' : '#475569',
            }}
          >
            仅显示选中
          </button>
        </div>
      </div>

      {/* Canvas 区域 */}
      <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        <Canvas
          camera={{
            position: [camDist * 0.7, camDist * 0.6, camDist * 0.7],
            fov: 45,
            near: 10,
            far: camDist * 10,
          }}
          gl={{ 
            antialias: true,
            alpha: false,
            powerPreference: 'high-performance',
          }}
          shadows
        >
          <Suspense fallback={null}>
            <SceneInner
              result={result}
              container={container}
              selectedId={selectedId}
              hiddenIds={hiddenIds}
              onSelect={setSelectedId}
              onToggleHide={toggleHide}
              cameraTarget={cameraTarget}
              onCameraArrived={handleCameraArrived}
              distanceFactor={maxDim * 0.8}
            />
          </Suspense>
        </Canvas>

        {/* 图例面板 */}
        {result && itemIds.length > 0 && (
          <div
            style={{
              position: 'absolute',
              top: 12,
              right: 12,
              background: 'rgba(255,255,255,0.96)',
              borderRadius: 8,
              padding: '10px 12px',
              boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
              border: '1px solid #e2e8f0',
              minWidth: 160,
              zIndex: 10,
            }}
          >
            <div style={{
              fontSize: 12,
              fontWeight: 600,
              marginBottom: 8,
              color: '#0f172a',
              borderBottom: '1px solid #e2e8f0',
              paddingBottom: 6,
            }}>
              商品图例
            </div>
            {itemIds.map((id, i) => (
              <div
                key={id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '3px 0',
                  cursor: 'pointer',
                  opacity: hiddenIds.has(id) ? 0.4 : 1,
                  fontWeight: selectedId === id ? 600 : 400,
                }}
                onClick={() => {
                  setSelectedId(selectedId === id ? null : id);
                }}
              >
                <div
                  style={{
                    width: 14,
                    height: 14,
                    borderRadius: 3,
                    background: COLORS[i % COLORS.length],
                    border: selectedId === id ? '2px solid #0f172a' : '1px solid #cbd5e1',
                  }}
                />
                <span style={{ fontSize: 12, color: '#334155' }}>{id}</span>
                <button
                  style={{
                    marginLeft: 'auto',
                    fontSize: 11,
                    border: '1px solid #e2e8f0',
                    borderRadius: 4,
                    background: '#fff',
                    color: '#64748b',
                    cursor: 'pointer',
                    padding: '1px 6px',
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleHidden(id);
                  }}
                >
                  {hiddenIds.has(id) ? '显示' : '隐藏'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
