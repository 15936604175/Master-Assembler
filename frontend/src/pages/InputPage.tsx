import { useState } from 'react';
import { Button, Card, message, Radio, Space, Typography, Tooltip } from 'antd';
import { PlayCircleOutlined, ThunderboltOutlined, BulbOutlined, EyeOutlined } from '@ant-design/icons';
import ContainerConfig from '../components/ContainerConfig';
import ItemListEditor from '../components/ItemListEditor';
import type { ItemRow } from '../components/ItemListEditor';
import BoxLoader from '../components/BoxLoader';
import { optimizeBlock, optimizeAdvancedBlock } from '../services/api';
import type { OptimizeResponse, ContainerConfig as ContainerConfigType, ItemInput } from '../types';

const { Title, Text } = Typography;

type Algorithm = 'advanced_block' | 'block';

interface InputPageProps {
  onOptimizeComplete: (
    result: OptimizeResponse,
    container?: ContainerConfigType
  ) => void;
  container: ContainerConfigType;
  setContainer: (v: ContainerConfigType) => void;
  items: ItemRow[];
  setItems: (v: ItemRow[]) => void;
  algorithm: Algorithm;
  setAlgorithm: (v: Algorithm) => void;
  existingResult?: OptimizeResponse | null;
}

export default function InputPage({
  onOptimizeComplete,
  container,
  setContainer,
  items,
  setItems,
  algorithm,
  setAlgorithm,
  existingResult,
}: InputPageProps) {
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState('正在优化装配方案...');

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

    // 检查 ID 是否重复
    const ids = items.map(item => item.id);
    const duplicateIds = ids.filter((id, index) => ids.indexOf(id) !== index);
    if (duplicateIds.length > 0) {
      message.error(`商品 ID 重复: ${duplicateIds.join(', ')}，请修改后再计算`);
      return;
    }

    setLoading(true);
    if (algorithm === 'advanced_block') {
      setLoadingText('高级 Block 优化中（Batch Corridor + Beam Search）...');
    } else {
      setLoadingText('Block 块状优化中...');
    }
    try {
      const inputItems = buildItems();
      if (algorithm === 'advanced_block') {
        const result = await optimizeAdvancedBlock({ container, items: inputItems });
        onOptimizeComplete(result, container);
        message.success(`高级 Block 优化完成 (利用率 ${(result.container_utilization * 100).toFixed(1)}%，耗时 ${result.stats.algorithm_time_ms}ms)`);
      } else {
        const result = await optimizeBlock({ container, items: inputItems });
        onOptimizeComplete(result, container);
        message.success(`Block 优化完成 (利用率 ${(result.container_utilization * 100).toFixed(1)}%，耗时 ${result.stats.algorithm_time_ms}ms)`);
      }
    } catch (err: unknown) {
      const error = err as Error;
      // 解析后端返回的错误信息
      let errorMsg = '优化请求失败，请检查后端服务是否启动';
      try {
        const match = error.message.match(/API error \(422\): (.+)/);
        if (match) {
          const detail = JSON.parse(match[1]);
          if (detail.detail?.errors) {
            errorMsg = `数据验证失败: ${detail.detail.errors.join(', ')}`;
          } else if (detail.detail?.message) {
            errorMsg = detail.detail.message;
          }
        } else if (error.message.includes('API error')) {
          errorMsg = error.message.replace('API error', '优化失败');
        }
      } catch {
        // 无法解析，使用原始错误信息
        if (error.message) {
          errorMsg = error.message;
        }
      }
      message.error(errorMsg);
      console.error('优化错误:', error);
    } finally {
      setLoading(false);
    }
  };

  // 查看上次优化结果（不重新计算）
  const handleViewExisting = () => {
    if (existingResult) {
      onOptimizeComplete(existingResult, container);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: '#f1f5f9',
      display: 'flex',
      flexDirection: 'column',
      position: 'relative',
    }}>
      {/* 优化计算加载动画覆盖层 */}
      {loading && (
        <div style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(241, 245, 249, 0.92)',
          backdropFilter: 'blur(4px)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <BoxLoader text={loadingText} />
        </div>
      )}
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
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: '#1d4ed8',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontWeight: 700, fontSize: 14,
          }}>
            XI
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#0f172a' }}>箱智</div>
            <div style={{ fontSize: 11, color: '#64748b' }}>X-Intelligence · 集装箱装载优化系统</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Text style={{ fontSize: 13, color: '#64748b' }}>参数配置</Text>
          <div style={{ width: 1, height: 16, background: '#e2e8f0' }} />
          <Text style={{ fontSize: 13, color: '#94a3b8' }}>优化结果</Text>
        </div>
      </div>

      {/* 主内容区 */}
      <div style={{
        flex: 1,
        padding: '24px 32px',
        maxWidth: 1400,
        width: '100%',
        margin: '0 auto',
      }}>
        <div style={{ marginBottom: 20 }}>
          <Title level={4} style={{ marginBottom: 4, color: '#0f172a' }}>参数配置</Title>
          <Text style={{ fontSize: 13, color: '#64748b' }}>
            配置集装箱尺寸与商品信息，选择优化算法后开始计算
          </Text>
        </div>

        <Space direction="vertical" size={20} style={{ width: '100%' }}>
          {/* 集装箱配置卡片 */}
          <Card
            title="集装箱配置"
            size="small"
            headStyle={{ borderBottom: '1px solid #e2e8f0' }}
          >
            <ContainerConfig value={container} onChange={setContainer} />
          </Card>

          {/* 商品列表卡片 */}
          <Card
            title={`商品列表 ${items.length > 0 ? `(${items.length})` : ''}`}
            size="small"
            headStyle={{ borderBottom: '1px solid #e2e8f0' }}
          >
            <ItemListEditor value={items} onChange={setItems} />
          </Card>

          {/* 算法选择卡片 */}
          <Card
            title="优化算法"
            size="small"
            headStyle={{ borderBottom: '1px solid #e2e8f0' }}
          >
            <Radio.Group
              value={algorithm}
              onChange={(e) => setAlgorithm(e.target.value)}
              style={{ width: '100%' }}
            >
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    padding: 14,
                    border: algorithm === 'advanced_block' ? '2px solid #059669' : '1px solid #e2e8f0',
                    borderRadius: 8,
                    cursor: 'pointer',
                    background: algorithm === 'advanced_block' ? '#ecfdf5' : '#fff',
                    transition: 'all 0.2s',
                  }}
                >
                  <Radio value="advanced_block" style={{ marginTop: 2 }} />
                  <div style={{ flex: 1, marginLeft: 4 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <ThunderboltOutlined style={{ color: '#059669' }} />
                      <strong style={{ fontSize: 15, color: '#0f172a' }}>高级 Block 优化</strong>
                      <span style={{
                        fontSize: 11, padding: '1px 6px', borderRadius: 4,
                        background: '#d1fae5', color: '#059669', fontWeight: 500,
                      }}>
                        推荐
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: '#64748b', marginTop: 6, lineHeight: 1.6 }}>
                      企业级 V2：Batch Corridor 动态走廊 + Target Center + Sequence Penalty + Beam Search，自动形成正确批次顺序
                    </div>
                  </div>
                </label>

                <label
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    padding: 14,
                    border: algorithm === 'block' ? '2px solid #7c3aed' : '1px solid #e2e8f0',
                    borderRadius: 8,
                    cursor: 'pointer',
                    background: algorithm === 'block' ? '#f5f3ff' : '#fff',
                    transition: 'all 0.2s',
                  }}
                >
                  <Radio value="block" style={{ marginTop: 2 }} />
                  <div style={{ flex: 1, marginLeft: 4 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <BulbOutlined style={{ color: '#7c3aed' }} />
                      <strong style={{ fontSize: 15, color: '#0f172a' }}>Block 块状优化</strong>
                    </div>
                    <div style={{ fontSize: 12, color: '#64748b', marginTop: 6, lineHeight: 1.6 }}>
                      V1 基础版：同SKU聚集 + 物理稳定性 + 批次分层，速度快利用率高
                    </div>
                  </div>
                </label>
              </Space>
            </Radio.Group>
          </Card>

          {/* 优化按钮区 */}
          {existingResult ? (
            <Space style={{ width: '100%' }} size={12}>
              <Button
                size="large"
                icon={<EyeOutlined />}
                onClick={handleViewExisting}
                disabled={loading}
                style={{
                  height: 48,
                  fontSize: 15,
                  fontWeight: 600,
                  borderRadius: 8,
                  flex: 1,
                }}
              >
                查看上次结果
              </Button>
              <Button
                type="primary"
                size="large"
                icon={<PlayCircleOutlined />}
                onClick={handleOptimize}
                disabled={loading}
                style={{
                  height: 48,
                  fontSize: 15,
                  fontWeight: 600,
                  borderRadius: 8,
                  flex: 1,
                }}
              >
                {loading ? '优化计算中...' : '重新优化'}
              </Button>
            </Space>
          ) : (
            <Button
              type="primary"
              size="large"
              icon={<PlayCircleOutlined />}
              onClick={handleOptimize}
              disabled={loading}
              block
              style={{
                height: 48,
                fontSize: 15,
                fontWeight: 600,
                borderRadius: 8,
              }}
            >
              {loading ? '优化计算中...' : '开始优化'}
            </Button>
          )}
        </Space>
      </div>
    </div>
  );
}
