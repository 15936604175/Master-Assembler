import { useState } from 'react';
import { Button, Card, message, Radio, Space } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import ContainerConfig from './ContainerConfig';
import ItemListEditor from './ItemListEditor';
import type { ItemRow } from './ItemListEditor';
import { optimize, optimizeBlock, optimizePhase2 } from '../services/api';
import type { OptimizeResponse, MultiOptimizeResponse, ContainerConfig as ContainerConfigType, ItemInput } from '../types';

type Algorithm = 'greedy' | 'block' | 'phase2';

interface ControlPanelProps {
  onResult: (result: OptimizeResponse) => void;
  onMultiResult?: (result: MultiOptimizeResponse) => void;
  onLoading: (loading: boolean) => void;
}

export default function ControlPanel({ onResult, onMultiResult, onLoading }: ControlPanelProps) {
  const [container, setContainer] = useState<ContainerConfigType>({
    length: 5898, width: 2352, height: 2395, max_weight: 28000,
  });
  const [items, setItems] = useState<ItemRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [algorithm, setAlgorithm] = useState<Algorithm>('block');

  const buildItems = (): ItemInput[] =>
    items.map((item) => ({
      id: item.id,
      length: item.length,
      width: item.width,
      height: item.height,
      weight: item.weight,
      quantity: item.quantity,
      is_fragile: item.is_fragile || false,
      batch_number: item.batch_number ?? 0,
      forbidden_horizontal_dims: item.forbidden_horizontal_dims ?? [],
    }));

  const handleOptimize = async () => {
    if (items.length === 0) {
      message.warning('请至少添加一个商品');
      return;
    }
    setLoading(true);
    onLoading(true);
    try {
      const inputItems = buildItems();
      if (algorithm === 'phase2') {
        message.info('Phase 2 优化预计需要 30-60 秒，请耐心等待...');
        const result = await optimizePhase2(
          { container, items: inputItems },
          { timeout_seconds: 60 }
        );
        onMultiResult?.(result);
        onResult(result.primary);
        message.success(`优化完成 (${result.pareto_count} 个帕累托方案，耗时 ${result.algorithm_time_ms}ms)`);
      } else if (algorithm === 'block') {
        const result = await optimizeBlock({ container, items: inputItems });
        onResult(result);
        message.success(`Block 优化完成 (利用率 ${(result.container_utilization * 100).toFixed(1)}%，耗时 ${result.stats.algorithm_time_ms}ms)`);
      } else {
        const result = await optimize({ container, items: inputItems });
        onResult(result);
        message.success('贪心优化完成');
      }
    } catch (err) {
      message.error('优化请求失败，请检查后端服务是否启动');
    } finally {
      setLoading(false);
      onLoading(false);
    }
  };

  return (
    <Card title="装配大师" style={{ minWidth: 320, height: '100%', overflowY: 'auto' }}>
      <ContainerConfig value={container} onChange={setContainer} />
      <ItemListEditor value={items} onChange={setItems} />
      <Radio.Group
        value={algorithm}
        onChange={(e) => setAlgorithm(e.target.value)}
        style={{ marginBottom: 8, display: 'block' }}
      >
        <Space direction="vertical">
          <Radio value="block">
            <strong>Block 块状优化</strong>
            <span style={{ fontSize: 12, color: '#888', marginLeft: 8 }}>
              企业级引擎（推荐）
            </span>
          </Radio>
          <Radio value="phase2">
            <strong>Phase 2 智能优化</strong>
            <span style={{ fontSize: 12, color: '#888', marginLeft: 8 }}>
              GA + 局部搜索 + 帕累托 + Block
            </span>
          </Radio>
          <Radio value="greedy">
            <strong>Phase 1 贪心算法</strong>
            <span style={{ fontSize: 12, color: '#888', marginLeft: 8 }}>
              快速基本优化
            </span>
          </Radio>
        </Space>
      </Radio.Group>
      <Button
        type="primary"
        size="large"
        icon={<PlayCircleOutlined />}
        onClick={handleOptimize}
        disabled={loading}
        block
        style={{ marginTop: 4 }}
      >
        {loading ? '优化中...' : '开始优化'}
      </Button>
    </Card>
  );
}
