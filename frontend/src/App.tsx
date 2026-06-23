import { useState, useEffect, useCallback } from 'react';
import { ConfigProvider, message, Button, Tooltip } from 'antd';
import {
  PlayCircleOutlined, DeleteOutlined,
  DownloadOutlined, FileAddOutlined,
  SettingOutlined, QuestionCircleOutlined,
} from '@ant-design/icons';
import LeftPanel from './components/LeftPanel';
import CenterView from './components/CenterView';
import RightPanel from './components/RightPanel';
import BoxLoader from './components/BoxLoader';
import { optimizeBlock, optimizeAdvancedBlock } from './services/api';
import { checkForUpdate } from './utils/updateCheck';
import type { OptimizeResponse, ContainerConfig, ItemInput } from './types';
import type { ItemRow } from './components/ItemListEditor';
import './App.css';

type Algorithm = 'advanced_block' | 'block';
type AppStatus = 'ready' | 'computing' | 'done' | 'error';

export default function App() {
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [container, setContainer] = useState<ContainerConfig>({
    length: 12032, width: 2352, height: 2695, max_weight: 28000,
  });
  const [items, setItems] = useState<ItemRow[]>([]);
  const [algorithm, setAlgorithm] = useState<Algorithm>('advanced_block');
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState('');
  const [status, setStatus] = useState<AppStatus>('ready');
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    checkForUpdate().then((release) => {
      if (release) {
        message.info(`发现新版本 ${release.tag_name}，请前往 GitHub 下载`, 8);
      }
    });
  }, []);

  const buildItems = (): ItemInput[] =>
    items.map((item) => ({
      id: item.id, length: item.length, width: item.width, height: item.height,
      weight: item.weight, quantity: item.quantity,
      is_fragile: item.is_fragile || false,
      batch_number: item.batch_number ?? 0,
      forbidden_horizontal_dims: item.forbidden_horizontal_dims ?? [],
    }));

  const handleOptimize = useCallback(async () => {
    if (items.length === 0) { message.warning('请至少添加一个商品'); return; }
    const ids = items.map(i => i.id);
    const dups = ids.filter((id, idx) => ids.indexOf(id) !== idx);
    if (dups.length > 0) { message.error(`商品 ID 重复: ${dups.join(', ')}`); return; }

    setLoading(true);
    setStatus('computing');
    setLoadingText(algorithm === 'advanced_block' ? '高级 Block 优化中...' : 'Block 块状优化中...');

    try {
      const inputItems = buildItems();
      const r = algorithm === 'advanced_block'
        ? await optimizeAdvancedBlock({ container, items: inputItems })
        : await optimizeBlock({ container, items: inputItems });
      setResult(r);
      setElapsed(r.stats.algorithm_time_ms);
      setStatus('done');
      message.success(`优化完成 · 利用率 ${(r.container_utilization * 100).toFixed(1)}% · ${r.stats.algorithm_time_ms.toFixed(0)}ms`);
    } catch (err: unknown) {
      const error = err as Error;
      let errorMsg = '优化请求失败，请检查后端服务';
      try {
        const match = error.message.match(/API error \(\d+\): (.+)/);
        if (match) {
          const detail = JSON.parse(match[1]);
          errorMsg = detail.detail?.errors?.join(', ') || detail.detail?.message || errorMsg;
        }
      } catch { /* fallback */ }
      message.error(errorMsg);
      setStatus('error');
    } finally {
      setLoading(false);
      setTimeout(() => setStatus(result ? 'done' : 'ready'), 3000);
    }
  }, [items, container, algorithm, result]);

  const handleClear = () => {
    setResult(null);
    setStatus('ready');
    setElapsed(0);
  };

  const handleExport = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'packing_result.json'; a.click();
    URL.revokeObjectURL(url);
  };

  const statusText = status === 'computing' ? '计算中...' : status === 'done' ? '计算完成 ✓' : status === 'error' ? '出错' : '就绪';
  const statusColor = status === 'computing' ? 'var(--accent-orange)' : status === 'done' ? 'var(--accent-green)' : status === 'error' ? 'var(--accent-red)' : 'var(--text-secondary)';

  return (
    <ConfigProvider theme={{
      algorithm: undefined,
      token: {
        colorPrimary: '#4A90E2', colorSuccess: '#50C878', colorWarning: '#FFB347',
        colorError: '#FF6B6B', colorInfo: '#4A90E2',
        borderRadius: 4, fontFamily: "var(--font-main)", fontSize: 13,
        controlHeight: 32, wireframe: false,
        colorBgContainer: '#25252E', colorBgElevated: '#2A2A35',
        colorBgLayout: '#1E1E24', colorBorder: '#3E3E42',
        colorBorderSecondary: '#3E3E42', colorText: '#E0E0E0',
        colorTextSecondary: '#A0A0A0', colorTextTertiary: '#666666',
      },
      components: {
        Table: { headerBg: '#2A2A35', headerColor: '#A0A0A0', headerSplitColor: '#3E3E42',
          rowHoverBg: '#32323E', borderColor: '#3E3E42', cellPaddingBlock: 8, cellPaddingInline: 10 },
        Input: { borderRadius: 4, controlHeight: 32 },
        InputNumber: { borderRadius: 4, controlHeight: 32 },
        Select: { borderRadius: 4, controlHeight: 32 },
        Button: { borderRadius: 4, controlHeight: 32, fontWeight: 500 },
        Tag: { borderRadiusSM: 3 },
      },
    }}>
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-primary)' }}>
        {/* 顶部工具栏 */}
        <div style={{
          height: 48, background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', padding: '0 16px', gap: 8, flexShrink: 0,
        }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginRight: 16 }}>
            <div style={{ width: 28, height: 28, borderRadius: 6, background: 'var(--accent-blue)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontWeight: 700, fontSize: 12 }}>MA</div>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>装配大师</span>
          </div>

          <div style={{ width: 1, height: 20, background: 'var(--border)' }} />

          {/* 文件操作 */}
          <Tooltip title="新建"><Button type="text" size="small" icon={<FileAddOutlined />} style={{ color: 'var(--text-secondary)' }} onClick={() => { setItems([]); handleClear(); }} /></Tooltip>
          <Tooltip title="导出"><Button type="text" size="small" icon={<DownloadOutlined />} style={{ color: 'var(--text-secondary)' }} onClick={handleExport} disabled={!result} /></Tooltip>

          <div style={{ flex: 1 }} />

          {/* 计算控制 */}
          {result && <Button icon={<DeleteOutlined />} onClick={handleClear} size="small">清空</Button>}

          <div style={{ width: 1, height: 20, background: 'var(--border)' }} />
          <Tooltip title="设置"><Button type="text" size="small" icon={<SettingOutlined />} style={{ color: 'var(--text-secondary)' }} /></Tooltip>
          <Tooltip title="帮助"><Button type="text" size="small" icon={<QuestionCircleOutlined />} style={{ color: 'var(--text-secondary)' }} /></Tooltip>
        </div>

        {/* 主内容区：三栏 */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
          {/* 左侧面板 */}
          <div style={{
            width: 340, flexShrink: 0, borderRight: '1px solid var(--border)',
            background: 'var(--bg-secondary)', display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}>
            <LeftPanel
              container={container} setContainer={setContainer}
              items={items} setItems={setItems}
              algorithm={algorithm} setAlgorithm={setAlgorithm}
              onOptimize={handleOptimize} loading={loading}
            />
          </div>

          {/* 中央视图 */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
            <CenterView result={result} container={container} loading={loading} loadingText={loadingText} />
          </div>

          {/* 右侧面板 */}
          <div style={{
            width: 300, flexShrink: 0, borderLeft: '1px solid var(--border)',
            background: 'var(--bg-secondary)', overflowY: 'auto', overflowX: 'hidden',
          }}>
            <RightPanel result={result} container={container} />
          </div>
        </div>

        {/* 底部状态栏 */}
        <div style={{
          height: 28, background: 'var(--bg-primary)', borderTop: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 16px', fontSize: 11, flexShrink: 0,
        }}>
          <span style={{ color: statusColor, fontWeight: 500 }}>{statusText}</span>
          <div style={{ display: 'flex', gap: 16, color: 'var(--text-secondary)' }}>
            {result && <>
              <span>{result.solution_type === 'advanced_block' ? '高级Block' : 'Block优化'}</span>
              <span>利用率 {(result.container_utilization * 100).toFixed(1)}%</span>
              <span>{elapsed.toFixed(0)}ms</span>
            </>}
          </div>
        </div>
      </div>
    </ConfigProvider>
  );
}
