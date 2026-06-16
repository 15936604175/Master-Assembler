import { Button, InputNumber, Table, Card } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

export interface ItemRow {
  key: string;
  id: string;
  length: number;
  width: number;
  height: number;
  weight: number;
  quantity: number;
  is_fragile?: boolean;
  batch_number?: number;
  forbidden_horizontal_dim?: 'length' | 'width' | 'height' | null;
}

interface ItemListEditorProps {
  value: ItemRow[];
  onChange: (items: ItemRow[]) => void;
}

const genId = (index: number) => String.fromCharCode(65 + (index % 26));

/** 朝向模式定义 */
const ORIENTATION_MODES = [
  {
    key: 'standard',
    label: 'Standard',
    labelCN: '标准放置',
    forbidden: null as 'length' | 'width' | 'height' | null,
    rotations: [
      { angle: 0, label: '0°', dims: (l: number, w: number, h: number) => ({ dx: l, dy: h, dz: w }) },
      { angle: 90, label: '90°', dims: (l: number, w: number, h: number) => ({ dx: w, dy: h, dz: l }) },
    ],
  },
  {
    key: 'turn_up',
    label: 'Turn up',
    labelCN: '竖立放置',
    forbidden: 'length' as const,
    rotations: [
      { angle: 0, label: '0°', dims: (l: number, w: number, h: number) => ({ dx: w, dy: l, dz: h }) },
      { angle: 90, label: '90°', dims: (l: number, w: number, h: number) => ({ dx: h, dy: l, dz: w }) },
    ],
  },
  {
    key: 'turn_side',
    label: 'Turn side',
    labelCN: '侧向放置',
    forbidden: 'width' as const,
    rotations: [
      { angle: 0, label: '0°', dims: (l: number, w: number, h: number) => ({ dx: l, dy: w, dz: h }) },
      { angle: 90, label: '90°', dims: (l: number, w: number, h: number) => ({ dx: h, dy: w, dz: l }) },
    ],
  },
];

/** 蓝色风格3D盒子 - 模仿参考软件 */
function BlueCube3D({ dx, dy, dz, checked }: {
  dx: number; dy: number; dz: number; checked?: boolean;
}) {
  const max = Math.max(dx, dy, dz);
  const scale = 32 / max;
  const sx = dx * scale;
  const sy = dy * scale;
  const sz = dz * scale;

  // 等轴测投影矩阵
  const project = ([x, y, z]: number[]) => ({
    px: x * 0.866 - z * 0.5,
    py: x * 0.5 + y * z * 0.866,
  });

  const topFace = [[0,sy,0], [sx,sy,0], [sx,sy,sz], [0,sy,sz]].map(project);
  const frontFace = [[0,0,0], [sx,0,0], [sx,sy,0], [0,sy,0]].map(project);
  const rightFace = [[sx,0,0], [sx,0,sz], [sx,sy,sz], [sx,sy,0]].map(project);

  const toPoly = (pts: typeof frontFace) =>
    pts.map(p => `${p.px},${p.py}`).join(' ');

  const allPts = [...topFace, ...frontFace, ...rightFace];
  const minX = Math.min(...allPts.map(p => p.px)), maxX = Math.max(...allPts.map(p => p.px));
  const minY = Math.min(...allPts.map(p => p.py)), maxY = Math.max(...allPts.map(p => p.py));
  const offX = -(minX + maxX) / 2;
  const offY = -(minY + maxY) / 2;

  const transform = `translate(${offX + 28}px, ${offY + 34}px)`;
  const fillBase = checked ? '#2563eb' : '#3b82f6';
  const fillLight = checked ? '#60a5fa' : '#93c5fd';
  const strokeColor = checked ? '#1e40af' : '#2563eb';

  return (
    <svg width="56" height="68" style={{ display: 'block' }}>
      <g transform={transform}>
        {/* 顶面 */}
        <polygon points={toPoly(topFace)} fill={fillLight} stroke={strokeColor} strokeWidth="0.8" />
        {/* 前面 */}
        <polygon points={toPoly(frontFace)} fill={fillBase} stroke={strokeColor} strokeWidth="0.8" />
        {/* 右面 */}
        <polygon points={toPoly(rightFace)} fill={checked ? '#3b82f6' : '#60a5fa'} stroke={strokeColor} strokeWidth="0.8" />
      </g>
    </svg>
  );
}

/** 朝向选择器 - 模仿参考软件UI */
function OrientationSelector({ item, onUpdate }: {
  item: ItemRow;
  onUpdate: (field: keyof ItemRow, val: any) => void;
}) {
  const selectedMode = item.forbidden_horizontal_dim;

  const handleSelect = (modeKey: string | null) => {
    if (selectedMode === modeKey) {
      // 点击已选中的模式取消选择 → 无约束
      onUpdate('forbidden_horizontal_dim', null);
    } else {
      // 选择新模式
      const mode = ORIENTATION_MODES.find(m => m.key === modeKey);
      onUpdate('forbidden_horizontal_dim', mode?.forbidden ?? null);
    }
  };

  return (
    <div style={{
      display: 'flex',
      gap: 16,
      padding: '8px 12px',
      background: '#fafafa',
      borderRadius: 6,
      border: '1px solid #e8e8e8',
    }}>
      {ORIENTATION_MODES.map((mode) => {
        const isSelected = selectedMode === mode.forbidden;
        return (
          <div
            key={mode.key}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              minWidth: 100,
            }}
          >
            {/* 标题 */}
            <div style={{
              fontSize: 11,
              fontWeight: 600,
              color: isSelected ? '#1677ff' : '#666',
              marginBottom: 6,
              textAlign: 'center',
            }}>
              {mode.label}
              <div style={{ fontSize: 10, fontWeight: 400, color: '#999' }}>{mode.labelCN}</div>
            </div>

            {/* 两个角度选项 */}
            <div style={{ display: 'flex', gap: 4 }}>
              {mode.rotations.map((rot) => {
                const isChecked = isSelected; // 该模式下都选中
                return (
                  <div
                    key={rot.angle}
                    onClick={() => handleSelect(mode.key)}
                    style={{
                      cursor: 'pointer',
                      padding: 4,
                      borderRadius: 4,
                      border: isSelected ? '2px solid #1677ff' : '1px solid #d9d9d9',
                      background: isSelected ? '#f0f5ff' : '#fff',
                      transition: 'all 0.15s',
                    }}
                  >
                    <BlueCube3D
                      dx={rot.dims(item.length, item.width, item.height).dx}
                      dy={rot.dims(item.length, item.width, item.height).dy}
                      dz={rot.dims(item.length, item.width, item.height).dz}
                      checked={isChecked}
                    />
                    {/* 角度标签 */}
                    <div style={{
                      textAlign: 'center',
                      fontSize: 10,
                      color: isSelected ? '#1677ff' : '#999',
                      fontWeight: isSelected ? 600 : 400,
                      marginTop: 2,
                    }}>
                      {rot.label}
                    </div>
                    {/* 复选框 */}
                    <div style={{
                      display: 'flex',
                      justifyContent: 'center',
                      marginTop: 2,
                    }}>
                      <svg width="14" height="14" viewBox="0 0 16 16">
                        <rect
                          x="0.5" y="0.5" width="15" height="15"
                          rx="3"
                          fill={isChecked ? '#1677ff' : '#fff'}
                          stroke={isChecked ? '#1677ff' : '#d9d9d9'}
                          strokeWidth="1.2"
                        />
                        {isChecked && (
                          <path
                            d="M4 8 L7 11 L12 5"
                            fill="none"
                            stroke="#fff"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        )}
                      </svg>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function ItemListEditor({ value, onChange }: ItemListEditorProps) {
  const addItem = () => {
    const newItem: ItemRow = {
      key: Date.now().toString(),
      id: genId(value.length),
      length: 100,
      width: 100,
      height: 100,
      weight: 10,
      quantity: 1,
      is_fragile: false,
      batch_number: 0,
      forbidden_horizontal_dim: null,
    };
    onChange([...value, newItem]);
  };

  const removeItem = (key: string) => {
    const next = value
      .filter((item) => item.key !== key)
      .map((item, i) => ({ ...item, id: genId(i) }));
    onChange(next);
  };

  const updateItem = (key: string, field: keyof ItemRow, val: any) => {
    onChange(value.map((item) => (item.key === key ? { ...item, [field]: val } : item)));
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 50 },
    { title: '长', width: 70,
      render: (_: any, record: ItemRow) => (
        <InputNumber
          size="small"
          defaultValue={record.length}
          min={1}
          onChange={(v) => { if (v) updateItem(record.key, 'length', v); }}
        />
      ),
    },
    { title: '宽', width: 70,
      render: (_: any, record: ItemRow) => (
        <InputNumber
          size="small"
          defaultValue={record.width}
          min={1}
          onChange={(v) => { if (v) updateItem(record.key, 'width', v); }}
        />
      ),
    },
    { title: '高', width: 70,
      render: (_: any, record: ItemRow) => (
        <InputNumber
          size="small"
          defaultValue={record.height}
          min={1}
          onChange={(v) => { if (v) updateItem(record.key, 'height', v); }}
        />
      ),
    },
    { title: '重量', width: 70,
      render: (_: any, record: ItemRow) => (
        <InputNumber
          size="small"
          defaultValue={record.weight}
          min={0.1}
          step={0.1}
          onChange={(v) => { if (v) updateItem(record.key, 'weight', v); }}
        />
      ),
    },
    { title: '数量', width: 70,
      render: (_: any, record: ItemRow) => (
        <InputNumber
          size="small"
          defaultValue={record.quantity}
          min={1}
          onChange={(v) => { if (v) updateItem(record.key, 'quantity', v); }}
        />
      ),
    },
    { title: '批次', width: 65,
      render: (_: any, record: ItemRow) => (
        <InputNumber
          size="small"
          defaultValue={record.batch_number ?? 0}
          min={0}
          onChange={(v) => { if (v !== undefined) updateItem(record.key, 'batch_number', v); }}
        />
      ),
    },
    { title: '易碎', width: 65,
      render: (_: any, record: ItemRow) => (
        <input
          type="checkbox"
          defaultChecked={record.is_fragile}
          onChange={(e) => updateItem(record.key, 'is_fragile', e.target.checked)}
          style={{ cursor: 'pointer' }}
        />
      ),
    },
    { title: '朝向约束', width: 170,
      render: (_: any, record: ItemRow) => (
        <OrientationSelector
          item={record}
          onUpdate={(field, val) => updateItem(record.key, field, val)}
        />
      ),
    },
    { title: '', width: 45,
      render: (_: any, record: ItemRow) => (
        <Button
          size="small"
          danger
          icon={<DeleteOutlined />}
          onClick={() => removeItem(record.key)}
        />
      ),
    },
  ];

  return (
    <Card title="商品列表" size="small" style={{ marginBottom: 16 }}>
      <Table
        dataSource={value}
        columns={columns}
        pagination={false}
        size="small"
        scroll={{ x: 1050 }}
        rowKey="key"
      />
      <Button
        type="dashed"
        onClick={addItem}
        icon={<PlusOutlined />}
        style={{ width: '100%', marginTop: 8 }}
      >
        添加商品
      </Button>
    </Card>
  );
}
