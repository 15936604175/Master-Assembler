import { useState } from 'react';
import { Button, InputNumber, Input, Tooltip, Checkbox } from 'antd';
import { PlusOutlined, DeleteOutlined, CopyOutlined } from '@ant-design/icons';

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

const genId = (index: number) => {
  if (index < 26) return String.fromCharCode(65 + index);
  const first = Math.floor(index / 26) - 1;
  const second = index % 26;
  return String.fromCharCode(65 + first) + String.fromCharCode(65 + second);
};

/** 等轴测3D长方体 */
function IsoCube3D({ dx, dy, dz, checked }: {
  dx: number; dy: number; dz: number; checked?: boolean;
}) {
  const longest = Math.max(dx, dy, dz);
  const targetPx = Math.min(28, Math.max(14, 10 + Math.log(longest) * 3.5));
  const scale = targetPx / longest;
  const sx = dx * scale, sy = dy * scale, sz = dz * scale;
  const c = Math.cos(Math.PI / 6), s = Math.sin(Math.PI / 6);
  const p = (x: number, y: number, z: number) => ({ px: (x - z) * c, py: (x + z) * s - y });
  const toPts = (poly: number[][]) =>
    poly.map(v => `${p(v[0],v[1],v[2]).px.toFixed(1)},${p(v[0],v[1],v[2]).py.toFixed(1)}`).join(' ');

  const color = checked ? '#4A90E2' : '#666666';
  const alpha = '55';
  const faceData = [
    { pts: [[0,0,sz],[sx,0,sz],[sx,sy,sz],[0,sy,sz]], fill: '#6b7280' + alpha },
    { pts: [[0,0,0],[0,0,sz],[0,sy,sz],[0,sy,0]],     fill: '#8b5cf6' + alpha },
    { pts: [[0,0,0],[sx,0,0],[sx,0,sz],[0,0,sz]],     fill: '#f59e0b' + alpha },
    { pts: [[0,sy,0],[sx,sy,0],[sx,sy,sz],[0,sy,sz]], fill: '#10b981' + alpha },
    { pts: [[sx,0,0],[sx,0,sz],[sx,sy,sz],[sx,sy,0]], fill: '#ec4899' + alpha },
    { pts: [[0,0,0],[sx,0,0],[sx,sy,0],[0,sy,0]],     fill: color + alpha },
  ];
  const edgePairs = [[0,1],[2,4],[3,5],[6,7],[0,2],[1,4],[3,6],[5,7],[0,3],[1,5],[2,6],[4,7]];
  const verts = [p(0,0,0),p(sx,0,0),p(0,sy,0),p(0,0,sz),p(sx,sy,0),p(sx,0,sz),p(0,sy,sz),p(sx,sy,sz)];
  const allPx = verts.map(v => v.px), allPy = verts.map(v => v.py);
  const minX = Math.min(...allPx), maxX = Math.max(...allPx);
  const minY = Math.min(...allPy), maxY = Math.max(...allPy);
  const svgW = Math.max(30, Math.ceil(maxX - minX) + 6);
  const svgH = Math.max(30, Math.ceil(maxY - minY) + 6);
  const tx = -(minX + maxX) / 2 + svgW / 2, ty = -(minY + maxY) / 2 + svgH / 2;
  const strokeColor = checked ? '#4A90E2' : '#555555';

  return (
    <svg width={svgW} height={svgH} style={{ display: 'block' }}>
      <g transform={`translate(${tx.toFixed(1)},${ty.toFixed(1)})`}>
        {faceData.map((d, i) => <polygon key={i} points={toPts(d.pts)} fill={d.fill} stroke="none" />)}
        {edgePairs.map((pair, k) => {
          const [i, j] = pair;
          return <line key={k} x1={verts[i].px} y1={verts[i].py} x2={verts[j].px} y2={verts[j].py}
            stroke={strokeColor} strokeWidth="1" strokeLinecap="round" />;
        })}
      </g>
    </svg>
  );
}

/* 朝向选择器 */
function OrientationSelector({ item, onUpdate }: {
  item: ItemRow;
  onUpdate: (field: keyof ItemRow, val: any) => void;
}) {
  const forbiddenDims = item.forbidden_horizontal_dims ?? [];
  const toggleMode = (dim: string) => {
    if (forbiddenDims.includes(dim)) {
      onUpdate('forbidden_horizontal_dims', forbiddenDims.filter(d => d !== dim));
    } else {
      if (forbiddenDims.length >= 2) return;
      onUpdate('forbidden_horizontal_dims', [...forbiddenDims, dim]);
    }
  };
  const modes = [
    { key: 'a', forbid: 'height', fn: (l: number, w: number, h: number) => ({ dx: l, dy: h, dz: w }) },
    { key: 'b', forbid: 'length', fn: (l: number, w: number, h: number) => ({ dx: w, dy: l, dz: h }) },
    { key: 'c', forbid: 'width',  fn: (l: number, w: number, h: number) => ({ dx: l, dy: w, dz: h }) },
  ];

  return (
    <div style={{ display: 'flex', gap: 6 }}>
      {modes.map((mode) => {
        const disabled = forbiddenDims.includes(mode.forbid);
        const { dx, dy, dz } = mode.fn(item.length, item.width, item.height);
        return (
          <div key={mode.key} onClick={() => toggleMode(mode.forbid)} style={{
            cursor: 'pointer', padding: '2px 4px', borderRadius: 4,
            border: disabled ? '2px solid var(--accent-red)' : '2px solid var(--accent-blue)',
            background: disabled ? 'rgba(255,107,107,0.08)' : 'rgba(74,144,226,0.08)',
            opacity: disabled ? 0.5 : 1, userSelect: 'none',
          }}>
            <IsoCube3D dx={dx} dy={dy} dz={dz} checked={!disabled} />
          </div>
        );
      })}
    </div>
  );
}

/* 属性编辑栏的行组件 */
function PropRow({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
      <div style={{ width: 64, fontSize: 12, color: 'var(--text-secondary)', flexShrink: 0, textAlign: 'right' }}>
        {label}
      </div>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
        {children}
      </div>
      {hint && <div style={{ fontSize: 10, color: 'var(--text-disabled)', flexShrink: 0 }}>{hint}</div>}
    </div>
  );
}

export default function ItemListEditor({ value, onChange }: ItemListEditorProps) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const selectedItem = value.find(item => item.key === selectedKey) ?? null;

  const addItem = () => {
    const existingIds = new Set(value.map(item => item.id));
    let newId = '', index = value.length;
    do { newId = genId(index); index++; } while (existingIds.has(newId));
    const newItem: ItemRow = {
      key: Date.now().toString(), id: newId,
      length: 100, width: 100, height: 100, weight: 10, quantity: 1,
      is_fragile: false, batch_number: 0, forbidden_horizontal_dims: [],
    };
    onChange([...value, newItem]);
    setSelectedKey(newItem.key);
  };

  const removeItem = (key: string) => {
    const remaining = value.filter(item => item.key !== key);
    const existingIds = new Set<string>();
    const next = remaining.map((item, i) => {
      let newId = '', idx = i;
      do { newId = genId(idx); idx++; } while (existingIds.has(newId));
      existingIds.add(newId);
      return { ...item, id: newId };
    });
    onChange(next);
    if (selectedKey === key) setSelectedKey(next.length > 0 ? next[0].key : null);
  };

  const duplicateItem = (key: string) => {
    const src = value.find(item => item.key === key);
    if (!src) return;
    const existingIds = new Set(value.map(item => item.id));
    let newId = '', index = value.length;
    do { newId = genId(index); index++; } while (existingIds.has(newId));
    const newItem: ItemRow = { ...src, key: Date.now().toString(), id: newId };
    const idx = value.findIndex(item => item.key === key);
    const next = [...value];
    next.splice(idx + 1, 0, newItem);
    onChange(next);
    setSelectedKey(newItem.key);
  };

  const updateItem = (key: string, field: keyof ItemRow, val: any) => {
    onChange(value.map(item => item.key === key ? { ...item, [field]: val } : item));
  };

  const inputStyle: React.CSSProperties = {
    background: 'var(--bg-primary)',
    borderColor: 'var(--border)',
    color: 'var(--text-primary)',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 紧凑商品列表 */}
      <div style={{ flex: selectedItem ? '0 0 auto' : 1, overflow: 'auto', minHeight: 0, maxHeight: selectedItem ? '40%' : '100%' }}>
        {value.map((item) => {
          const isSelected = item.key === selectedKey;
          const otherIds = value.filter(i => i.key !== item.key).map(i => i.id);
          const isDuplicate = otherIds.includes(item.id);
          return (
            <div
              key={item.key}
              onClick={() => setSelectedKey(isSelected ? null : item.key)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '8px 10px', cursor: 'pointer',
                borderBottom: '1px solid var(--border)',
                background: isSelected ? 'rgba(74,144,226,0.12)' : 'transparent',
                borderLeft: isSelected ? '3px solid var(--accent-blue)' : '3px solid transparent',
                transition: 'all 0.15s',
              }}
            >
              {/* 3D 缩略图 */}
              <div style={{ flexShrink: 0 }}>
                <IsoCube3D dx={item.length} dy={item.height} dz={item.width} checked={isSelected} />
              </div>
              {/* 商品信息 */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    fontWeight: 600, fontSize: 13,
                    color: isDuplicate ? 'var(--accent-red)' : 'var(--text-primary)',
                  }}>
                    {item.id}
                  </span>
                  {item.is_fragile && (
                    <span style={{
                      fontSize: 9, padding: '0 4px', borderRadius: 3,
                      background: 'rgba(255,179,71,0.15)', color: 'var(--accent-orange)',
                    }}>易碎</span>
                  )}
                  {item.quantity > 1 && (
                    <span style={{
                      fontSize: 9, padding: '0 4px', borderRadius: 3,
                      background: 'rgba(74,144,226,0.12)', color: 'var(--accent-blue)',
                    }}>×{item.quantity}</span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                  {item.length}×{item.width}×{item.height} mm · {item.weight} kg
                </div>
              </div>
              {/* 操作 */}
              <div style={{ display: 'flex', gap: 2, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
                <Button type="text" size="small" icon={<CopyOutlined />}
                  style={{ color: 'var(--text-disabled)', padding: '2px 4px' }}
                  onClick={() => duplicateItem(item.key)} />
                <Button type="text" size="small" icon={<DeleteOutlined />} danger
                  style={{ padding: '2px 4px' }}
                  onClick={() => removeItem(item.key)} />
              </div>
            </div>
          );
        })}

        {value.length === 0 && (
          <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-disabled)', fontSize: 12 }}>
            暂无商品，点击下方按钮添加
          </div>
        )}
      </div>

      {/* 选中商品属性编辑栏 */}
      {selectedItem && (
        <div style={{
          flex: 1, minHeight: 0, overflow: 'auto',
          borderTop: '2px solid var(--accent-blue)',
          background: 'var(--bg-tertiary)',
          padding: '12px 14px',
        }}>
          <div style={{
            fontSize: 12, fontWeight: 600, color: 'var(--accent-blue)',
            marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span style={{
              width: 20, height: 20, borderRadius: 4, background: 'var(--accent-blue)',
              color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700,
            }}>{selectedItem.id}</span>
            属性编辑
          </div>

          {/* ID */}
          <PropRow label="编号">
            <Input
              size="small"
              value={selectedItem.id}
              onChange={(e) => updateItem(selectedItem.key, 'id', e.target.value)}
              style={{ ...inputStyle, width: '100%' }}
            />
          </PropRow>

          {/* 长 */}
          <PropRow label="长度" hint="mm">
            <InputNumber size="small" value={selectedItem.length} min={1}
              onChange={(v) => v && updateItem(selectedItem.key, 'length', v)}
              style={{ ...inputStyle, width: '100%' }} />
          </PropRow>

          {/* 宽 */}
          <PropRow label="宽度" hint="mm">
            <InputNumber size="small" value={selectedItem.width} min={1}
              onChange={(v) => v && updateItem(selectedItem.key, 'width', v)}
              style={{ ...inputStyle, width: '100%' }} />
          </PropRow>

          {/* 高 */}
          <PropRow label="高度" hint="mm">
            <InputNumber size="small" value={selectedItem.height} min={1}
              onChange={(v) => v && updateItem(selectedItem.key, 'height', v)}
              style={{ ...inputStyle, width: '100%' }} />
          </PropRow>

          {/* 重量 */}
          <PropRow label="重量" hint="kg">
            <InputNumber size="small" value={selectedItem.weight} min={0.1} step={0.1}
              onChange={(v) => v && updateItem(selectedItem.key, 'weight', v)}
              style={{ ...inputStyle, width: '100%' }} />
          </PropRow>

          {/* 数量 */}
          <PropRow label="数量">
            <InputNumber size="small" value={selectedItem.quantity} min={1}
              onChange={(v) => v && updateItem(selectedItem.key, 'quantity', v)}
              style={{ ...inputStyle, width: '100%' }} />
          </PropRow>

          {/* 批次 */}
          <PropRow label="批次">
            <InputNumber size="small" value={selectedItem.batch_number ?? 0} min={0}
              onChange={(v) => v !== undefined && updateItem(selectedItem.key, 'batch_number', v)}
              style={{ ...inputStyle, width: '100%' }} />
            <Tooltip title="相同批次的商品优先放在一起">
              <span style={{ fontSize: 10, color: 'var(--text-disabled)', cursor: 'help' }}>?</span>
            </Tooltip>
          </PropRow>

          {/* 易碎 */}
          <PropRow label="易碎">
            <Checkbox
              checked={selectedItem.is_fragile ?? false}
              onChange={(e) => updateItem(selectedItem.key, 'is_fragile', e.target.checked)}
            >
              <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>标记为易碎品</span>
            </Checkbox>
          </PropRow>

          {/* 朝向约束 */}
          <PropRow label="朝向">
            <OrientationSelector
              item={selectedItem}
              onUpdate={(field, val) => updateItem(selectedItem.key, field, val)}
            />
          </PropRow>

          {/* 体积信息 */}
          <div style={{
            marginTop: 8, padding: '8px 10px', borderRadius: 4,
            background: 'var(--bg-primary)', border: '1px solid var(--border)',
            fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8,
          }}>
            <div>单件体积: <strong style={{ color: 'var(--text-primary)' }}>
              {(selectedItem.length * selectedItem.width * selectedItem.height / 1e9).toFixed(4)} m³
            </strong></div>
            <div>总体积: <strong style={{ color: 'var(--text-primary)' }}>
              {(selectedItem.length * selectedItem.width * selectedItem.height * selectedItem.quantity / 1e9).toFixed(4)} m³
            </strong></div>
            <div>总重量: <strong style={{ color: 'var(--text-primary)' }}>
              {(selectedItem.weight * selectedItem.quantity).toFixed(1)} kg
            </strong></div>
          </div>
        </div>
      )}

      {/* 添加按钮 */}
      <div style={{ flexShrink: 0, padding: '8px 0' }}>
        <Button type="dashed" onClick={addItem} icon={<PlusOutlined />}
          style={{ width: '100%', borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
          添加商品
        </Button>
      </div>
    </div>
  );
}
