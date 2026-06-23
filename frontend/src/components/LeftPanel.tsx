import { Tabs, Radio, Button, Space } from 'antd';
import { ThunderboltOutlined, BulbOutlined, PlayCircleOutlined } from '@ant-design/icons';
import ContainerConfig from './ContainerConfig';
import ItemListEditor from './ItemListEditor';
import type { ItemRow } from './ItemListEditor';
import type { ContainerConfig as ContainerConfigType } from '../types';

type Algorithm = 'advanced_block' | 'block';

interface LeftPanelProps {
  container: ContainerConfigType;
  setContainer: (v: ContainerConfigType) => void;
  items: ItemRow[];
  setItems: (v: ItemRow[]) => void;
  algorithm: Algorithm;
  setAlgorithm: (v: Algorithm) => void;
  onOptimize: () => void;
  loading: boolean;
}

const sectionStyle: React.CSSProperties = {
  padding: '12px 14px',
  overflowY: 'auto',
  flex: 1,
};

export default function LeftPanel({
  container, setContainer,
  items, setItems,
  algorithm, setAlgorithm,
  onOptimize, loading,
}: LeftPanelProps) {
  const tabItems = [
    {
      key: 'items',
      label: `商品 ${items.length > 0 ? `(${items.length})` : ''}`,
      children: (
        <div style={sectionStyle}>
          <ItemListEditor value={items} onChange={setItems} />
        </div>
      ),
    },
    {
      key: 'container',
      label: '集装箱',
      children: (
        <div style={sectionStyle}>
          <ContainerConfig value={container} onChange={setContainer} />
        </div>
      ),
    },
    {
      key: 'algorithm',
      label: '算法',
      children: (
        <div style={sectionStyle}>
          <Radio.Group
            value={algorithm}
            onChange={(e) => setAlgorithm(e.target.value)}
            style={{ width: '100%' }}
          >
            <Space direction="vertical" style={{ width: '100%' }} size={10}>
              <label style={{
                display: 'flex', alignItems: 'flex-start', padding: 12,
                border: algorithm === 'advanced_block' ? '1px solid var(--accent-green)' : '1px solid var(--border)',
                borderRadius: 6, cursor: 'pointer',
                background: algorithm === 'advanced_block' ? 'rgba(80,200,120,0.08)' : 'var(--bg-tertiary)',
                transition: 'all 0.2s',
              }}>
                <Radio value="advanced_block" style={{ marginTop: 2 }} />
                <div style={{ flex: 1, marginLeft: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <ThunderboltOutlined style={{ color: 'var(--accent-green)' }} />
                    <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>高级 Block</strong>
                    <span style={{
                      fontSize: 10, padding: '1px 5px', borderRadius: 3,
                      background: 'rgba(80,200,120,0.15)', color: 'var(--accent-green)', fontWeight: 500,
                    }}>推荐</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5 }}>
                    Batch Corridor + Beam Search，自动批次优化
                  </div>
                </div>
              </label>

              <label style={{
                display: 'flex', alignItems: 'flex-start', padding: 12,
                border: algorithm === 'block' ? '1px solid var(--accent-purple)' : '1px solid var(--border)',
                borderRadius: 6, cursor: 'pointer',
                background: algorithm === 'block' ? 'rgba(107,92,231,0.08)' : 'var(--bg-tertiary)',
                transition: 'all 0.2s',
              }}>
                <Radio value="block" style={{ marginTop: 2 }} />
                <div style={{ flex: 1, marginLeft: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <BulbOutlined style={{ color: 'var(--accent-purple)' }} />
                    <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>Block 块状</strong>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5 }}>
                    同SKU聚集 + 物理稳定性，速度快
                  </div>
                </div>
              </label>
            </Space>
          </Radio.Group>
        </div>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Tab 区域 */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <Tabs
          items={tabItems}
          size="small"
          style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
          tabBarStyle={{
            margin: 0, padding: '0 14px',
            background: 'var(--bg-secondary)',
            borderBottom: '1px solid var(--border)',
          }}
        />
      </div>

      {/* 底部计算按钮 */}
      <div style={{
        padding: '12px 14px', borderTop: '1px solid var(--border)',
        background: 'var(--bg-secondary)', flexShrink: 0,
      }}>
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={onOptimize}
          loading={loading}
          block
          style={{ height: 40, fontSize: 14, fontWeight: 600 }}
        >
          {loading ? '计算中...' : '开始计算'}
        </Button>
      </div>
    </div>
  );
}
