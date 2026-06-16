import { useState, Suspense } from 'react';
import { Button, Card, Typography, Space } from 'antd';
import { ArrowLeftOutlined, DownloadOutlined } from '@ant-design/icons';
import Layout3D from '../components/Layout3D';
import ResultPanel from '../components/ResultPanel';
import type { OptimizeResponse, ContainerConfig, MultiOptimizeResponse } from '../types';

const { Title, Text } = Typography;

interface ResultPageProps {
  result: OptimizeResponse;
  multiResult?: MultiOptimizeResponse | null;
  container: ContainerConfig;
  onBack: () => void;
}

export default function ResultPage({ result, multiResult, container, onBack }: ResultPageProps) {
  const [selectedResult, setSelectedResult] = useState<OptimizeResponse>(result);

  const handleExport = () => {
    const blob = new Blob([JSON.stringify(selectedResult, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'packing_result.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部导航栏 */}
      <div style={{
        background: '#fff',
        padding: '12px 24px',
        borderBottom: '1px solid #f0f0f0',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <Space>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={onBack}
          >
            返回配置
          </Button>
          <Title level={4} style={{ margin: 0 }}>
            装配大师 - 优化结果
          </Title>
        </Space>
        <Space>
          <Text type="secondary">
            算法: {selectedResult.solution_type || 'greedy'} | 
            利用率: {(selectedResult.container_utilization * 100).toFixed(2)}% |
            已放置: {selectedResult.stats.total_items_placed} 个
          </Text>
          <Button
            icon={<DownloadOutlined />}
            onClick={handleExport}
          >
            导出结果
          </Button>
        </Space>
      </div>

      {/* 3D 展示区域 */}
      <div style={{ flex: 1, minHeight: 0, background: '#f5f5f5' }}>
        <Suspense fallback={<div style={{ padding: 20 }}>加载 3D 场景...</div>}>
          <Layout3D result={selectedResult} container={container} />
        </Suspense>
      </div>

      {/* 结果面板 */}
      <div style={{
        height: 320,
        background: '#fff',
        borderTop: '1px solid #f0f0f0',
        padding: 16,
        overflowY: 'auto',
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