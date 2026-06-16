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
  cameraTarget: ViewPreset | null;
  onCameraArrived: () => void;
}

function SceneInner({
  result,
  container,
  selectedId,
  hiddenIds,
  onSelect,
  cameraTarget,
  onCameraArrived,
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

  // 计算每个商品的序号（同类商品的第几个）
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
          itemIndex={itemIndices.get(i)}
        />
      ))}
      <Grid
        position={[container.length / 2, 0, container.width / 2]}
        args={[container.length, container.width]}
        cellSize={Math.max(container.length, container.width) / 10}
        cellThickness={0.5}
        cellColor="#cccccc"
        sectionSize={Math.max(container.length, container.width) / 2}
        sectionThickness={1}
        sectionColor="#999999"
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

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        minHeight: 400,
        background: '#f5f5f5',
        position: 'relative',
      }}
    >
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
            cameraTarget={cameraTarget}
            onCameraArrived={handleCameraArrived}
          />
        </Suspense>
      </Canvas>

      {result && (
        <>
          <div
            style={{
              position: 'absolute',
              top: 12,
              right: 12,
              background: 'rgba(255,255,255,0.95)',
              borderRadius: 8,
              padding: 8,
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
              minWidth: 140,
              zIndex: 10,
            }}
          >
            <div
              style={{
                fontSize: 12,
                fontWeight: 'bold',
                marginBottom: 6,
                color: '#666',
              }}
            >
              商品列表
            </div>
            {itemIds.map((id, i) => (
              <div
                key={id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '2px 0',
                  cursor: 'pointer',
                  opacity: hiddenIds.has(id) ? 0.4 : 1,
                  fontWeight: selectedId === id ? 'bold' : 'normal',
                }}
                onClick={() => {
                  setSelectedId(selectedId === id ? null : id);
                }}
              >
                <div
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: 2,
                    background: COLORS[i % COLORS.length],
                    border: selectedId === id ? '2px solid #333' : 'none',
                  }}
                />
                <span style={{ fontSize: 12 }}>{id}</span>
                <button
                  style={{
                    marginLeft: 'auto',
                    fontSize: 10,
                    border: '1px solid #ccc',
                    borderRadius: 3,
                    background: '#fff',
                    cursor: 'pointer',
                    padding: '0 4px',
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

          <div
            style={{
              position: 'absolute',
              bottom: 12,
              left: '50%',
              transform: 'translateX(-50%)',
              display: 'flex',
              gap: 6,
              zIndex: 10,
              background: 'rgba(255,255,255,0.95)',
              padding: 8,
              borderRadius: 8,
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            }}
          >
            {viewPresets.map((preset) => (
              <button
                key={preset.id}
                onClick={() => handleViewPreset(preset)}
                style={{
                  padding: '6px 12px',
                  fontSize: 12,
                  border: '1px solid #ccc',
                  borderRadius: 6,
                  background: '#fff',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                {preset.label}
              </button>
            ))}
            <button
              onClick={() => {
                setSelectedId(null);
                setHiddenIds(new Set());
              }}
              style={{
                padding: '6px 12px',
                fontSize: 12,
                border: '1px solid #ccc',
                borderRadius: 6,
                background: '#fff',
                cursor: 'pointer',
              }}
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
                padding: '6px 12px',
                fontSize: 12,
                border: '1px solid #ccc',
                borderRadius: 6,
                background: selectedId ? '#e6f7ff' : '#fff',
                cursor: 'pointer',
              }}
            >
              仅显示选中
            </button>
          </div>
        </>
      )}
    </div>
  );
}
