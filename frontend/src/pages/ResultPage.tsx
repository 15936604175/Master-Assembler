import { useState, Suspense } from 'react';
import { Button, Card, Typography, Space, Tag, Tooltip, Checkbox } from 'antd';
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  InboxOutlined,
  AppstoreOutlined,
  TagOutlined,
} from '@ant-design/icons';
import Layout3D from '../components/Layout3D';
import ResultPanel from '../components/ResultPanel';
import type { OptimizeResponse, ContainerConfig, MultiOptimizeResponse } from '../types';

const { Text } = Typography;

interface ResultPageProps {
  result: OptimizeResponse;
  multiResult?: MultiOptimizeResponse | null;
  container: ContainerConfig;
  onBack: () => void;
}

export default function ResultPage({ result, multiResult, container, onBack }: ResultPageProps) {
  const [selectedResult, setSelectedResult] = useState<OptimizeResponse>(result);
  const [showLabels, setShowLabels] = useState(false);

  const handleExport = () => {
    const blob = new Blob([JSON.stringify(selectedResult, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'packing_result.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  const spaceUtil = (selectedResult.container_utilization * 100).toFixed(1);
  const weightUtil = (selectedResult.weight_utilization * 100).toFixed(1);
  const placedCount = selectedResult.stats.total_items_placed;
  const unplacedCount = selectedResult.stats.total_items_unplaced;
  const timeMs = selectedResult.stats.algorithm_time_ms.toFixed(0);

  // 指标卡片
  const metrics = [
    {
      label: '空间利用率',
      value: `${spaceUtil}%`,
      icon: <AppstoreOutlined />,
      color: Number(spaceUtil) >= 75 ? '#16a34a' : Number(spaceUtil) >= 50 ? '#d97706' : '#dc2626',
    },
    {
      label: '已放置',
      value: `${placedCount}`,
      unit: '件',
      icon: <CheckCircleOutlined />,
      color: '#16a34a',
    },
    {
      label: '未放置',
      value: `${unplacedCount}`,
      unit: '件',
      icon: <InboxOutlined />,
      color: unplacedCount > 0 ? '#dc2626' : '#16a34a',
    },
    {
      label: '计算耗时',
      value: `${timeMs}`,
      unit: 'ms',
      icon: <ClockCircleOutlined />,
      color: '#2563eb',
    },
  ];

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#f1f5f9' }}>
      {/* 顶部统一工具栏 */}
      <div style={{
        background: '#fff',
        padding: '0 24px',
        height: 56,
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={onBack}
            style={{ borderRadius: 8 }}
          >
            返回配置
          </Button>
          <div style={{ width: 1, height: 20, background: '#e2e8f0' }} />
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#0f172a' }}>装配大师 - 优化结果</div>
            <div style={{ fontSize: 11, color: '#64748b' }}>
              算法: {selectedResult.solution_type || 'greedy'}
            </div>
          </div>
        </div>
        <Space size={12}>
          <Tag color="blue" style={{ margin: 0 }}>
            方案: {selectedResult.solution_type || 'greedy'}
          </Tag>
          <Checkbox
            checked={showLabels}
            onChange={(e) => setShowLabels(e.target.checked)}
            style={{ fontSize: 13 }}
          >
            <TagOutlined style={{ marginRight: 2 }} />
            显示标签
          </Checkbox>
          <Tooltip title="导出 JSON 结果">
            <Button
              icon={<DownloadOutlined />}
              onClick={handleExport}
              style={{ borderRadius: 8 }}
            >
              导出
            </Button>
          </Tooltip>
        </Space>
      </div>

      {/* 指标卡片栏 */}
      <div style={{
        padding: '16px 24px',
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 16,
        flexShrink: 0,
      }}>
        {metrics.map((m, i) => (
          <Card key={i} size="small" style={{ borderRadius: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 40, height: 40, borderRadius: 8,
                background: `${m.color}15`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: m.color, fontSize: 18,
              }}>
                {m.icon}
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#64748b' }}>{m.label}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: '#0f172a', fontVariantNumeric: 'tabular-nums' }}>
                  {m.value}
                  {m.unit && <span style={{ fontSize: 13, fontWeight: 400, color: '#94a3b8', marginLeft: 4 }}>{m.unit}</span>}
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* 3D 展示区域 - CAD 风格卡片容器 */}
      <div style={{
        flex: 1,
        minHeight: 0,
        padding: '0 24px 16px',
        display: 'flex',
        flexDirection: 'column',
      }}>
        <Card
          size="small"
          style={{ flex: 1, borderRadius: 10, overflow: 'hidden' }}
          styles={{ body: { padding: 0, height: '100%' } }}
        >
          <Suspense fallback={<div style={{ padding: 20, color: '#64748b' }}>加载 3D 场景...</div>}>
            <Layout3D result={selectedResult} container={container} showLabels={showLabels} />
          </Suspense>
        </Card>
      </div>

      {/* 结果面板 - 专业后台表格 */}
      <div style={{
        height: 300,
        background: '#fff',
        borderTop: '1px solid #e2e8f0',
        padding: '12px 24px',
        overflowY: 'auto',
        flexShrink: 0,
      }}>
        <ResultPanel
          result={selectedResult}
          multiResult={multiResult}
          onSelectResult={setSelectedResult}
        />
      </div>
    </div>
  );
}
