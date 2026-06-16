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
  forbidden_horizontal_dims?: string[];
}

interface ItemListEditorProps {
  value: ItemRow[];
  onChange: (items: ItemRow[]) => void;
}

const genId = (index: number) => String.fromCharCode(65 + (index % 26));

/** 等轴测3D长方体（六面半透明 + 线框） */
function IsoCube3D({ dx, dy, dz, checked }: {
  dx: number; dy: number; dz: number; checked?: boolean;
}) {
  const max = Math.max(dx, dy, dz);
  const scale = 28 / max;
  const sx = dx * scale;
  const sy = dy * scale;
  const sz = dz * scale;

  const c = Math.cos(Math.PI / 6), s = Math.sin(Math.PI / 6);
  const p = (x: number, y: number, z: number) => ({
    px: (x - z) * c,
    py: (x + z) * s - y,
  });

  const pts = (poly: number[][]) =>
    poly.map((v) => `${p(v[0],v[1],v[2]).px.toFixed(1)},${p(v[0],v[1],v[2]).py.toFixed(1)}`).join(' ');

  // 六个面  渲染顺序: 后→左→下→上→右→前
  const color = checked ? '#3b82f6' : '#9ca3af';
  const alpha = '55';
  const faceData = [
    { pts: [[0,0,sz],[sx,0,sz],[sx,sy,sz],[0,sy,sz]], fill: '#6b7280' + alpha },
    { pts: [[0,0,0],[0,0,sz],[0,sy,sz],[0,sy,0]],     fill: '#8b5cf6' + alpha },
    { pts: [[0,0,0],[sx,0,0],[sx,0,sz],[0,0,sz]],     fill: '#f59e0b' + alpha },
    { pts: [[0,sy,0],[sx,sy,0],[sx,sy,sz],[0,sy,sz]], fill: '#10b981' + alpha },
    { pts: [[sx,0,0],[sx,0,sz],[sx,sy,sz],[sx,sy,0]], fill: '#ec4899' + alpha },
    { pts: [[0,0,0],[sx,0,0],[sx,sy,0],[0,sy,0]],     fill: color + alpha },
  ];

  // 12条棱
  const edgePairs = [
    [0,1],[2,4],[3,5],[6,7], [0,2],[1,4],[3,6],[5,7], [0,3],[1,5],[2,6],[4,7],
  ];
  const verts = [
    p(0,0,0), p(sx,0,0), p(0,sy,0), p(0,0,sz),
    p(sx,sy,0), p(sx,0,sz), p(0,sy,sz), p(sx,sy,sz),
  ];

  const allPx = verts.map(v => v.px), allPy = verts.map(v => v.py);
  const tx = -(Math.min(...allPx) + Math.max(...allPx)) / 2 + 28;
  const ty = -(Math.min(...allPy) + Math.max(...allPy)) / 2 + 30;

  const strokeColor = checked ? '#1d4ed8' : '#6b7280';

  return (
    <svg width={56} height={60} style={{ display: 'block' }}>
      <g transform={`translate(${tx.toFixed(1)},${ty.toFixed(1)})`}>
        {faceData.map((d, i) => (
          <polygon key={i} points={pts(d.pts)} fill={d.fill} stroke="none" />
        ))}
        {edgePairs.map((pair, k) => {
          const [i, j] = pair;
          return (
            <line key={k} x1={verts[i].px} y1={verts[i].py}
                  x2={verts[j].px} y2={verts[j].py}
                  stroke={strokeColor} strokeWidth="1" strokeLinecap="round" />
          );
        })}
      </g>
    </svg>
  );
}

function OrientationSelector({ item, onUpdate }: {
  item: ItemRow;
  onUpdate: (field: keyof ItemRow, val: any) => void;
}) {
  const forbiddenDims = item.forbidden_horizontal_dims ?? [];

  const isDisabled = (dim: string) => forbiddenDims.includes(dim);

  const toggleMode = (dim: string) => {
    if (isDisabled(dim)) {
      onUpdate('forbidden_horizontal_dims', forbiddenDims.filter(d => d !== dim));
    } else {
      onUpdate('forbidden_horizontal_dims', [...forbiddenDims, dim]);
    }
  };

  const modes = [
    { key: 'a', forbid: 'height', fn: (l: number, w: number, h: number) => ({ dx: l, dy: h, dz: w }) },
    { key: 'b', forbid: 'length', fn: (l: number, w: number, h: number) => ({ dx: w, dy: l, dz: h }) },
    { key: 'c', forbid: 'width',  fn: (l: number, w: number, h: number) => ({ dx: l, dy: w, dz: h }) },
  ];

  return (
    <div style={{
      display: 'flex', gap: 6, padding: '6px 8px',
      background: '#fafafa', borderRadius: 6, border: '1px solid #e8e8e8',
    }}>
      {modes.map((mode) => {
        const disabled = isDisabled(mode.forbid);
        const { dx, dy, dz } = mode.fn(item.length, item.width, item.height);
        return (
          <div key={mode.key} onClick={() => toggleMode(mode.forbid)} style={{
            cursor: 'pointer', padding: '4px 6px', borderRadius: 6,
            border: disabled ? '2px solid #ff4d4f' : '2px solid #1677ff',
            background: disabled ? '#fff2f0' : '#f0f5ff',
            opacity: disabled ? 0.65 : 1, userSelect: 'none',
          }}>
            <IsoCube3D dx={dx} dy={dy} dz={dz} checked={!disabled} />
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
      forbidden_horizontal_dims: [],
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
