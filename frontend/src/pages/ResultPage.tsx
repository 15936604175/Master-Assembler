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
import type { OptimizeResponse, ContainerConfig } from '../types';

const { Text } = Typography;

interface ResultPageProps {
  result: OptimizeResponse;
  container: ContainerConfig;
  onBack: () => void;
}

export default function ResultPage({ result, container, onBack }: ResultPageProps) {
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
      color: parseFloat(spaceUtil) >= 75 ? '#16a34a' : parseFloat(spaceUtil) >= 50 ? '#d97706' : '#dc2626',
    },
    {
      label: '载重利用率',
      value: `${weightUtil}%`,
      icon: <InboxOutlined />,
      color: parseFloat(weightUtil) >= 75 ? '#16a34a' : parseFloat(weightUtil) >= 50 ? '#d97706' : '#dc2626',
    },
    {
      label: '已放置',
      value: `${placedCount}`,
      icon: <CheckCircleOutlined />,
      color: '#1d4ed8',
    },
    {
      label: '未放置',
      value: `${unplacedCount}`,
      icon: <ClockCircleOutlined />,
      color: unplacedCount > 0 ? '#dc2626' : '#16a34a',
    },
    {
      label: '耗时',
      value: `${timeMs}ms`,
      icon: <ClockCircleOutlined />,
      color: '#64748b',
    },
  ];

  return (
    <div style={{
      minHeight: '100vh',
      background: '#f1f5f9',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* 顶部工具栏 */}
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
          <Button icon={<ArrowLeftOutlined />} onClick={onBack}>
            返回
          </Button>
          <div style={{ width: 1, height: 16, background: '#e2e8f0' }} />
          <Text style={{ fontSize: 15, fontWeight: 600, color: '#0f172a' }}>优化结果</Text>
          <Tag color={selectedResult.solution_type === 'advanced_block' ? 'green' : 'purple'}>
            {selectedResult.solution_type === 'advanced_block' ? '高级Block' : 'Block优化'}
          </Tag>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Checkbox
            checked={showLabels}
            onChange={(e) => setShowLabels(e.target.checked)}
          >
            显示标签
          </Checkbox>
          <Button icon={<DownloadOutlined />} onClick={handleExport}>
            导出结果
          </Button>
        </div>
      </div>

      {/* 指标卡片行 */}
      <div style={{
        padding: '16px 24px',
        background: '#fff',
        borderBottom: '1px solid #e2e8f0',
        flexShrink: 0,
      }}>
        <Space size={16} wrap>
          {metrics.map((m, i) => (
            <Card
              key={i}
              size="small"
              style={{
                width: 140,
                boxShadow: 'none',
                border: '1px solid #e2e8f0',
              }}
              bodyStyle={{ padding: '10px 12px' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: m.color, fontSize: 18 }}>{m.icon}</span>
                <div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>{m.label}</div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: '#0f172a' }}>{m.value}</div>
                </div>
              </div>
            </Card>
          ))}
        </Space>
      </div>

      {/* 主内容区：3D可视化 + 结果面板 */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* 3D可视化区域 */}
        <div style={{
          flex: 1,
          background: '#fff',
          borderBottom: '1px solid #e2e8f0',
        }}>
          <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>加载3D场景...</div>}>
            <Layout3D
              result={selectedResult}
              container={container}
              showLabels={showLabels}
            />
          </Suspense>
        </div>

        {/* 结果面板 */}
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
            onSelectResult={setSelectedResult}
          />
        </div>
      </div>
    </div>
  );
}