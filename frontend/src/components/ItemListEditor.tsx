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

/** 3D 盒子组件：纯视觉展示，无文字
 *  - 三个面可见（顶面 + 正面 + 右面）
 *  - 颜色区分三个轴向：X=红, Y=绿, Z=蓝
 *  - 通过 scale 让不同尺寸的物品按真实比例显示
 */
function Cube3D({ dx, dy, dz, selected }: {
  dx: number; dy: number; dz: number;
  selected: boolean;
}) {
  // 归一化：最长边映射到 36px
  const max = Math.max(dx, dy, dz);
  const scale = 36 / max;
  const sx = dx * scale;
  const sy = dy * scale;
  const sz = dz * scale;

  // 用于旋转后投影的 3D 坐标（Y 轴向上，X 向右，Z 向外）
  const topFace = [  // Y = sy（上顶面，从上方看）
    [0, sy, 0], [sx, sy, 0], [sx, sy, sz], [0, sy, sz],
  ];
  const frontFace = [  // Z = 0（前面，X×Y 平面）
    [0, 0, 0], [sx, 0, 0], [sx, sy, 0], [0, sy, 0],
  ];
  const rightFace = [  // X = sx（右侧，Y×Z 平面）
    [sx, 0, 0], [sx, 0, sz], [sx, sy, sz], [sx, sy, 0],
  ];

  // 等轴测投影：rotateX(60deg) rotateZ(-30deg) 的投影矩阵
  // 等效矩阵: x' = x*0.866 - z*0.5, y' = x*0.5 + y + z*0.866
  const project = ([x, y, z]: number[]) => ({
    px: x * 0.866 - z * 0.5,
    py: x * 0.5 + y - z * 0.866,
  });

  const pts = (face: number[][]) => face.map(project);

  const tp = pts(topFace);
  const fp = pts(frontFace);
  const rp = pts(rightFace);

  const toPoly = (pts: { px: number; py: number }[]) =>
    `${pts.map(p => `${p.px},${p.py}`).join(' ')}`;

  // 中心偏移，让三个面围成的形状居中
  const allX = [...tp, ...fp, ...rp].map(p => p.px);
  const allY = [...tp, ...fp, ...rp].map(p => p.py);
  const minX = Math.min(...allX), maxX = Math.max(...allX);
  const minY = Math.min(...allY), maxY = Math.max(...allY);
  const offX = -(minX + maxX) / 2;
  const offY = -(minY + maxY) / 2;

  const transform = `translate(${offX + 26}px, ${offY + 30}px)`;
  const borderColor = selected ? '#1890ff' : '#aaa';
  const strokeW = selected ? 2 : 1;

  return (
    <svg
      width={52}
      height={52}
      viewBox="-30 -5 60 55"
      style={{ overflow: 'visible', display: 'block' }}
    >
      <g transform={transform}>
        {/* 顶面 (Y 轴方向，绿色调) */}
        <polygon
          points={toPoly(tp)}
          fill={selected ? '#40a9ff' : '#91d5ff'}
          fillOpacity={0.5}
          stroke={borderColor}
          strokeWidth={strokeW}
        />
        {/* 前面 (Z 轴方向，蓝色调) */}
        <polygon
          points={toPoly(fp)}
          fill={selected ? '#096dd9' : '#1890ff'}
          fillOpacity={0.6}
          stroke={borderColor}
          strokeWidth={strokeW}
        />
        {/* 右面 (X 轴方向，红色调) */}
        <polygon
          points={toPoly(rp)}
          fill={selected ? '#0050b3' : '#40a9ff'}
          fillOpacity={0.5}
          stroke={borderColor}
          strokeWidth={strokeW}
        />
        {/* 顶点指示线 */}
        <line x1={fp[0].px} y1={fp[0].py} x2={tp[0].px} y2={tp[0].py}
          stroke={borderColor} strokeWidth={strokeW} opacity={0.4} />
        <line x1={fp[1].px} y1={fp[1].py} x2={tp[1].px} y2={tp[1].py}
          stroke={borderColor} strokeWidth={strokeW} opacity={0.4} />
        <line x1={fp[3].px} y1={fp[3].py} x2={tp[3].px} y2={tp[3].py}
          stroke={borderColor} strokeWidth={strokeW} opacity={0.4} />
        <line x1={rp[0].px} y1={rp[0].py} x2={tp[0].px} y2={tp[0].py}
          stroke={borderColor} strokeWidth={strokeW} opacity={0.4} />
        <line x1={rp[1].px} y1={rp[1].py} x2={tp[1].px} y2={tp[1].py}
          stroke={borderColor} strokeWidth={strokeW} opacity={0.4} />
        <line x1={rp[3].px} y1={rp[3].py} x2={tp[3].px} y2={tp[3].py}
          stroke={borderColor} strokeWidth={strokeW} opacity={0.4} />
      </g>
    </svg>
  );
}

/** 三种朝向选项：高度垂直 / 宽度垂直 / 长度垂直 */
const ORIENTATIONS = [
  { forbidden: null as 'length' | 'width' | 'height' | null, hint: '无约束' },
  { forbidden: 'height' as const, hint: '高度垂直' },
  { forbidden: 'width' as const, hint: '宽度垂直' },
  { forbidden: 'length' as const, hint: '长度垂直' },
];

/** 朝向选择器：三个 3D 盒子，点击选中 */
function OrientationSelector({ item, onUpdate }: {
  item: ItemRow;
  onUpdate: (field: keyof ItemRow, val: any) => void;
}) {
  const selected = item.forbidden_horizontal_dim;

  // 三种朝向的 (X尺寸, Y尺寸/高度, Z尺寸)
  // 顶视图: X-Z 平面 → 底面
  // 前视图: X-Y 平面 → 侧面（高度沿Y轴向上）
  // 3D展示时约定: width=深度(Z), height=高度(Y), length=宽度(X)
  const orientations = [
    { dims: { dx: item.length, dy: item.height, dz: item.width } },  // 高度垂直: 底 L×W
    { dims: { dx: item.length, dy: item.width, dz: item.height } },   // 宽度垂直: 底 L×H
    { dims: { dx: item.width, dy: item.length, dz: item.height } },   // 长度垂直: 底 W×H
  ];

  return (
    <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
      {/* 三个 3D 盒子 */}
      {orientations.map((o, i) => {
        const orient = ORIENTATIONS[i + 1]; // +1 跳过"无约束"
        const isForbidden = selected === orient.forbidden;
        return (
          <div
            key={i}
            onClick={() => onUpdate('forbidden_horizontal_dim', isForbidden ? null : orient.forbidden)}
            style={{
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              padding: '2px 3px',
              borderRadius: 4,
              border: isForbidden ? '2px solid #1890ff' : '1px solid #e8e8e8',
              background: isForbidden ? '#e6f7ff' : '#fff',
              opacity: selected !== null && !isForbidden ? 0.35 : 1,
              transition: 'all 0.15s',
            }}
            title={orient.hint}
          >
            <Cube3D
              dx={o.dims.dx}
              dy={o.dims.dy}
              dz={o.dims.dz}
              selected={isForbidden}
            />
            {/* 垂直轴指示：顶部小三角 */}
            {isForbidden && (
              <div style={{
                width: 0, height: 0,
                borderLeft: '4px solid transparent',
                borderRight: '4px solid transparent',
                borderBottom: '5px solid #1890ff',
                marginTop: -2,
              }} />
            )}
          </div>
        );
      })}
      {/* "无约束" 选项 */}
      <div
        onClick={() => onUpdate('forbidden_horizontal_dim', null)}
        style={{
          cursor: 'pointer',
          width: 14,
          height: 14,
          borderRadius: '50%',
          border: selected === null ? '2px solid #1890ff' : '1px solid #d9d9d9',
          background: selected === null ? '#1890ff' : 'transparent',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
        title="无约束"
      />
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
