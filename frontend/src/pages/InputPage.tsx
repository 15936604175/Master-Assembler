import { useState } from 'react';
import { Button, Card, message, Radio, Space, Typography, Result } from 'antd';
import { PlayCircleOutlined, SettingOutlined } from '@ant-design/icons';
import ContainerConfig from '../components/ContainerConfig';
import ItemListEditor from '../components/ItemListEditor';
import type { ItemRow } from '../components/ItemListEditor';
import { optimize, optimizePhase2 } from '../services/api';
import type { OptimizeResponse, MultiOptimizeResponse, ContainerConfig as ContainerConfigType, ItemInput } from '../types';

const { Title, Paragraph } = Typography;

type Algorithm = 'greedy' | 'phase2';

interface InputPageProps {
  onOptimizeComplete: (
    result: OptimizeResponse,
    multiResult?: MultiOptimizeResponse | null,
    container?: ContainerConfigType
  ) => void;
}

export default function InputPage({ onOptimizeComplete }: InputPageProps) {
  const [container, setContainer] = useState<ContainerConfigType>({
    length: 5898, width: 2352, height: 2395, max_weight: 28000,
  });
  const [items, setItems] = useState<ItemRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [algorithm, setAlgorithm] = useState<Algorithm>('phase2');

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
      forbidden_horizontal_dim: item.forbidden_horizontal_dim ?? null,
    }));

  const handleOptimize = async () => {
    if (items.length === 0) {
      message.warning('请至少添加一个商品');
      return;
    }
    setLoading(true);
    try {
      const inputItems = buildItems();
      if (algorithm === 'phase2') {
        message.info('Phase 2 优化预计需要 30-60 秒，请耐心等待...');
        const result = await optimizePhase2(
          { container, items: inputItems },
          { timeout_seconds: 60 }
        );
        onOptimizeComplete(result.primary, result, container);
        message.success(`优化完成 (${result.pareto_count} 个帕累托方案，耗时 ${result.algorithm_time_ms}ms)`);
      } else {
        const result = await optimize({ container, items: inputItems });
        onOptimizeComplete(result, null, container);
        message.success('优化完成');
      }
    } catch (err) {
      message.error('优化请求失败，请检查后端服务是否启动');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      padding: '40px 20px',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'flex-start',
    }}>
      <Card
        style={{
          maxWidth: 900,
          width: '100%',
          boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
          borderRadius: 12,
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Title level={2} style={{ marginBottom: 8 }}>
            <SettingOutlined style={{ marginRight: 8 }} />
            装配大师 - 参数配置
          </Title>
          <Paragraph style={{ color: '#666', fontSize: 14 }}>
            配置集装箱尺寸和商品信息，开始智能装箱优化
          </Paragraph>
        </div>

        <div style={{ marginBottom: 24 }}>
          <Title level={4}>集装箱配置</Title>
          <ContainerConfig value={container} onChange={setContainer} />
        </div>

        <div style={{ marginBottom: 24 }}>
          <Title level={4}>商品列表</Title>
          <ItemListEditor value={items} onChange={setItems} />
        </div>

        <div style={{ marginBottom: 24 }}>
          <Title level={4}>优化算法</Title>
          <Radio.Group
            value={algorithm}
            onChange={(e) => setAlgorithm(e.target.value)}
            style={{ width: '100%' }}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <Radio value="phase2" style={{ padding: 12, border: '1px solid #f0f0f0', borderRadius: 6 }}>
                <div>
                  <strong style={{ fontSize: 16 }}>Phase 2 智能优化</strong>
                  <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                    遗传算法 + 局部搜索 + 帕累托多目标优化
                    <br />
                    提供多个优化方案供对比选择
                  </div>
                </div>
              </Radio>
              <Radio value="greedy" style={{ padding: 12, border: '1px solid #f0f0f0', borderRadius: 6 }}>
                <div>
                  <strong style={{ fontSize: 16 }}>Phase 1 贪心算法</strong>
                  <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                    快速基本优化，适合大量商品场景
                  </div>
                </div>
              </Radio>
            </Space>
          </Radio.Group>
        </div>

        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          onClick={handleOptimize}
          disabled={loading}
          block
          style={{
            height: 48,
            fontSize: 16,
            fontWeight: 'bold',
            marginTop: 16,
          }}
        >
          {loading ? '优化计算中...' : '开始优化'}
        </Button>

        {items.length === 0 && (
          <div style={{ marginTop: 24 }}>
            <Result
              status="info"
              title="开始配置"
              subTitle="请添加至少一个商品，然后点击开始优化"
            />
          </div>
        )}
      </Card>
    </div>
  );
}