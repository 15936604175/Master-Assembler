import { Progress, Space } from 'antd';

interface UtilizationBarProps {
  spaceUtil: number;
  weightUtil: number;
  totalWeight: number;
}

export default function UtilizationBar({ spaceUtil, weightUtil, totalWeight }: UtilizationBarProps) {
  const spacePct = Math.round(spaceUtil * 100);
  const weightPct = Math.round(weightUtil * 100);

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>空间利用率</span>
          <span>{spacePct}%</span>
        </div>
        <Progress
          percent={spacePct}
          strokeColor={spacePct >= 75 ? '#52c41a' : spacePct >= 50 ? '#faad14' : '#f5222d'}
        />
      </div>
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>载重利用率</span>
          <span>{weightPct}% ({totalWeight.toFixed(1)} kg)</span>
        </div>
        <Progress
          percent={weightPct}
          strokeColor={weightPct >= 75 ? '#52c41a' : weightPct >= 50 ? '#faad14' : '#f5222d'}
        />
      </div>
    </Space>
  );
}
