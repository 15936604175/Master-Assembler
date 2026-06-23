import { useState } from 'react';
import Layout3D from './Layout3D';
import Layout2D from './Layout2D';
import BoxLoader from './BoxLoader';
import type { OptimizeResponse, ContainerConfig } from '../types';

interface CenterViewProps {
  result: OptimizeResponse | null;
  container: ContainerConfig;
  loading?: boolean;
  loadingText?: string;
}

type ViewMode = '3d' | '2d';

export default function CenterView({ result, container, loading, loadingText }: CenterViewProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('3d');

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* 视图切换标签 */}
      <div style={{
        height: 36, background: 'var(--bg-tertiary)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', padding: '0 12px', gap: 4,
        flexShrink: 0,
      }}>
        {(['3d', '2d'] as ViewMode[]).map((mode) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            style={{
              padding: '4px 14px', fontSize: 12, fontWeight: 500,
              border: 'none', borderRadius: 4, cursor: 'pointer',
              background: viewMode === mode ? 'var(--accent-blue)' : 'transparent',
              color: viewMode === mode ? '#fff' : 'var(--text-secondary)',
              transition: 'all 0.2s',
            }}
          >
            {mode === '3d' ? '3D 视图' : '2D 视图'}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: 'var(--text-disabled)' }}>
          {container.length}×{container.width}×{container.height} mm
        </span>
      </div>

      {/* 视图内容 */}
      <div style={{ flex: 1, minHeight: 0, position: 'relative', display: 'flex', flexDirection: 'column' }}>
        {loading && (
          <div style={{
            position: 'absolute', inset: 0, zIndex: 100,
            background: 'rgba(30,30,36,0.85)', backdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <BoxLoader text={loadingText || ''} />
          </div>
        )}
        {viewMode === '3d' ? (
          <Layout3D result={result} container={container} />
        ) : (
          <Layout2D result={result} container={container} />
        )}
      </div>
    </div>
  );
}
