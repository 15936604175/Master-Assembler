import { Select, InputNumber, Row, Col } from 'antd';

const PRESETS = [
  { value: '20GP', label: '20尺普柜 (5898×2352×2395)', length: 5898, width: 2352, height: 2395, maxWeight: 28000 },
  { value: '40GP', label: '40尺普柜 (12032×2352×2395)', length: 12032, width: 2352, height: 2395, maxWeight: 28000 },
  { value: '40HQ', label: '40尺高柜 (12032×2352×2695)', length: 12032, width: 2352, height: 2695, maxWeight: 28000 },
];

interface ContainerConfigProps {
  value: { length: number; width: number; height: number; max_weight: number };
  onChange: (value: { length: number; width: number; height: number; max_weight: number }) => void;
}

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  color: '#64748b',
  marginBottom: 4,
};

export default function ContainerConfig({ value, onChange }: ContainerConfigProps) {
  const handlePreset = (presetId: string) => {
    const preset = PRESETS.find(p => p.value === presetId);
    if (preset) {
      onChange({ length: preset.length, width: preset.width, height: preset.height, max_weight: preset.maxWeight });
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <div style={labelStyle}>预设箱型</div>
        <Select
          placeholder="选择预设箱型"
          onChange={handlePreset}
          allowClear
          options={PRESETS}
          style={{ width: '100%' }}
        />
      </div>
      <Row gutter={16}>
        <Col span={6}>
          <div style={labelStyle}>长 (mm)</div>
          <InputNumber
            value={value.length}
            onChange={v => onChange({ ...value, length: v ?? 0 })}
            min={1}
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={6}>
          <div style={labelStyle}>宽 (mm)</div>
          <InputNumber
            value={value.width}
            onChange={v => onChange({ ...value, width: v ?? 0 })}
            min={1}
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={6}>
          <div style={labelStyle}>高 (mm)</div>
          <InputNumber
            value={value.height}
            onChange={v => onChange({ ...value, height: v ?? 0 })}
            min={1}
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={6}>
          <div style={labelStyle}>载重 (kg)</div>
          <InputNumber
            value={value.max_weight}
            onChange={v => onChange({ ...value, max_weight: v ?? 0 })}
            min={1}
            style={{ width: '100%' }}
          />
        </Col>
      </Row>
    </div>
  );
}
