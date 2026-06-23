import { useMemo } from 'react';
import { Tag, Tooltip, Progress } from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined,
  WarningOutlined, ExperimentOutlined,
} from '@ant-design/icons';
import type { OptimizeResponse, ContainerConfig } from '../types';

interface RightPanelProps {
  result: OptimizeResponse | null;
  container: ContainerConfig;
}

/* 环形进度条卡片 */
function RingCard({ title, value, color, suffix }: {
  title: string; value: number; color: string; suffix?: string;
}) {
  const pct = Math.round(value * 100);
  return (
    <div style={cardStyle}>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>{title}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Progress
          type="circle" percent={pct} size={56}
          strokeColor={color}
          trailColor="var(--bg-primary)"
          format={() => <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{pct}%</span>}
        />
        <div style={{ fontSize: 11, color: 'var(--text-disabled)' }}>{suffix}</div>
      </div>
    </div>
  );
}

/* 统计行 */
function StatRow({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12 }}>
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <span style={{ color: color || 'var(--text-primary)', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  background: 'var(--bg-tertiary)', borderRadius: 6,
  padding: '12px 14px', marginBottom: 8,
  border: '1px solid var(--border)',
};

/* 重心偏移简易箱体示意图 */
function CgDiagram({ offsetX, offsetZ, containerL, containerW }: {
  offsetX: number; offsetZ: number; containerL: number; containerW: number;
}) {
  const size = 80;
  const maxOffset = Math.max(containerL, containerW) / 2;
  const normX = Math.min(1, offsetX / maxOffset);
  const normZ = Math.min(1, offsetZ / maxOffset);
  const dotX = size / 2 + normX * (size / 2 - 6) * (offsetX >= 0 ? 1 : -1);
  const dotZ = size / 2 + normZ * (size / 2 - 6) * (offsetZ >= 0 ? 1 : -1);

  return (
    <svg width={size} height={size} style={{ display: 'block' }}>
      <rect x={2} y={2} width={size - 4} height={size - 4}
        fill="none" stroke="var(--border-light)" strokeWidth={1} rx={3} />
      {/* 中心十字 */}
      <line x1={size / 2} y1={size / 2 - 6} x2={size / 2} y2={size / 2 + 6}
        stroke="var(--text-disabled)" strokeWidth={0.8} />
      <line x1={size / 2 - 6} y1={size / 2} x2={size / 2 + 6} y2={size / 2}
        stroke="var(--text-disabled)" strokeWidth={0.8} />
      {/* 偏移点 */}
      <circle cx={dotX} cy={dotZ} r={4} fill="var(--accent-red)" />
      <circle cx={dotX} cy={dotZ} r={7} fill="none" stroke="var(--accent-red)" strokeWidth={1} opacity={0.4} />
      {/* 标签 */}
      <text x={size / 2} y={size - 3} textAnchor="middle" fontSize={8} fill="var(--text-disabled)">X→</text>
      <text x={5} y={size / 2} textAnchor="middle" fontSize={8} fill="var(--text-disabled)"
        transform={`rotate(-90, 5, ${size / 2})`}>Z→</text>
    </svg>
  );
}

export default function RightPanel({ result, container }: RightPanelProps) {
  // 计算重心偏移
  const cgOffset = useMemo(() => {
    if (!result) return null;
    const cg = result.center_of_gravity;
    const xOff = Math.abs(cg.x - container.length / 2);
    const zOff = Math.abs(cg.z - container.width / 2);
    const total = Math.sqrt(xOff * xOff + zOff * zOff);
    return { x: xOff, z: zOff, total };
  }, [result, container]);

  if (!result) {
    return (
      <div style={{ padding: '40px 14px', textAlign: 'center' }}>
        <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.3 }}>📦</div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>配置商品并开始计算</div>
        <div style={{ fontSize: 11, color: 'var(--text-disabled)', marginTop: 4 }}>结果统计将在此处显示</div>
      </div>
    );
  }

  const report = result.feasibility_report;
  const metrics = result.metrics;
  const totalItems = result.stats.total_items_placed + result.stats.total_items_unplaced;
  const totalWeight = container.max_weight;
  const loadedWeight = result.total_weight;

  return (
    <div style={{ padding: '12px 14px' }}>
      {/* 标题 */}
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12,
        display: 'flex', alignItems: 'center', gap: 8 }}>
        结果统计
        {result.solution_type && (
          <Tag color={result.solution_type === 'advanced_block' ? 'green' : 'purple'} style={{ margin: 0 }}>
            {result.solution_type === 'advanced_block' ? '高级Block' : 'Block'}
          </Tag>
        )}
      </div>

      {/* 卡片1: 空间利用率 */}
      <RingCard
        title="空间利用率"
        value={result.container_utilization}
        color={result.container_utilization >= 0.75 ? 'var(--accent-green)' : result.container_utilization >= 0.5 ? 'var(--accent-orange)' : 'var(--accent-red)'}
        suffix={`${(result.container_utilization * container.length * container.width * container.height / 1e9).toFixed(2)} m³`}
      />

      {/* 卡片2: 重量利用率 */}
      <RingCard
        title="重量利用率"
        value={result.weight_utilization}
        color={result.weight_utilization >= 0.75 ? 'var(--accent-blue)' : result.weight_utilization >= 0.5 ? 'var(--accent-orange)' : 'var(--accent-red)'}
        suffix={`${loadedWeight.toFixed(0)} / ${totalWeight} kg`}
      />

      {/* 卡片3: 货物统计 */}
      <div style={cardStyle}>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>货物统计</div>
        <StatRow label="已装载" value={result.stats.total_items_placed} color="var(--accent-green)" />
        <StatRow label="未装载" value={result.stats.total_items_unplaced}
          color={result.stats.total_items_unplaced > 0 ? 'var(--accent-red)' : 'var(--text-primary)'} />
        <StatRow label="总计" value={totalItems} />
      </div>

      {/* 卡片4: 重量统计 */}
      <div style={cardStyle}>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>重量统计</div>
        <StatRow label="已装载" value={`${loadedWeight.toFixed(0)} kg`} color="var(--accent-blue)" />
        <StatRow label="剩余载重" value={`${(totalWeight - loadedWeight).toFixed(0)} kg`} />
        <StatRow label="最大载重" value={`${totalWeight} kg`} />
      </div>

      {/* 卡片5: 重心偏移 */}
      {cgOffset && (
        <div style={cardStyle}>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>重心偏移</div>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <StatRow label="X 偏移" value={`${cgOffset.x.toFixed(0)} mm`}
                color={cgOffset.x > container.length * 0.1 ? 'var(--accent-orange)' : 'var(--accent-green)'} />
              <StatRow label="Y 偏移" value={`${cgOffset.z.toFixed(0)} mm`}
                color={cgOffset.z > container.width * 0.1 ? 'var(--accent-orange)' : 'var(--accent-green)'} />
              <StatRow label="综合偏移" value={`${cgOffset.total.toFixed(0)} mm`}
                color={cgOffset.total > Math.max(container.length, container.width) * 0.1 ? 'var(--accent-orange)' : 'var(--accent-green)'} />
              {result.cg_deviation_ratio !== undefined && (
                <StatRow label="偏移率" value={`${(result.cg_deviation_ratio * 100).toFixed(1)}%`}
                  color={result.cg_deviation_ratio < 0.15 ? 'var(--accent-green)' : 'var(--accent-orange)'} />
              )}
            </div>
            <CgDiagram
              offsetX={cgOffset.x} offsetZ={cgOffset.z}
              containerL={container.length} containerW={container.width}
            />
          </div>
        </div>
      )}

      {/* 卡片6: 可行性验证 */}
      {report && (
        <div style={cardStyle}>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8,
            display: 'flex', alignItems: 'center', gap: 6 }}>
            <ExperimentOutlined /> 可行性验证
            <Tag color={report.is_feasible ? 'green' : 'red'} style={{ margin: 0, marginLeft: 'auto' }}>
              {report.is_feasible ? '通过' : '失败'}
            </Tag>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            <Tooltip title="几何约束检查">
              <Tag color={report.geometry_ok ? 'green' : 'red'} style={{ margin: 0 }}>
                {report.geometry_ok ? <CheckCircleOutlined /> : <CloseCircleOutlined />} 几何
              </Tag>
            </Tooltip>
            <Tooltip title="物理约束检查">
              <Tag color={report.physics_ok ? 'green' : 'orange'} style={{ margin: 0 }}>
                {report.physics_ok ? <CheckCircleOutlined /> : <WarningOutlined />} 物理
              </Tag>
            </Tooltip>
            <Tooltip title="朝向约束检查">
              <Tag color={report.orientation_ok ? 'green' : 'orange'} style={{ margin: 0 }}>
                {report.orientation_ok ? <CheckCircleOutlined /> : <WarningOutlined />} 朝向
              </Tag>
            </Tooltip>
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11 }}>
            <Tooltip title="稳定性评分 (0-1)，越高越稳定">
              <span style={{ color: 'var(--text-secondary)' }}>
                稳定性: <strong style={{ color: 'var(--text-primary)' }}>{report.stability_score.toFixed(3)}</strong>
              </span>
            </Tooltip>
            <Tooltip title="支撑率 (0-1)，越高越稳固">
              <span style={{ color: 'var(--text-secondary)' }}>
                支撑率: <strong style={{ color: 'var(--text-primary)' }}>{report.support_score.toFixed(3)}</strong>
              </span>
            </Tooltip>
          </div>
          {report.messages.length > 0 && (
            <div style={{ marginTop: 6, fontSize: 11, color: 'var(--accent-orange)' }}>
              {report.messages.slice(0, 3).map((m, i) => (
                <div key={i}>· {m}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 指标补充 */}
      {metrics && (
        <div style={cardStyle}>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>辅助指标</div>
          <StatRow label="平均支撑率" value={`${(metrics.avg_support_ratio * 100).toFixed(0)}%`}
            color={metrics.avg_support_ratio >= 0.6 ? 'var(--accent-green)' : 'var(--accent-orange)'} />
          {metrics.fragile_violations > 0 && (
            <StatRow label="易碎品压迫" value={metrics.fragile_violations} color="var(--accent-red)" />
          )}
          <StatRow label="计算耗时" value={`${result.stats.algorithm_time_ms.toFixed(0)} ms`} />
        </div>
      )}

      {/* 卡片7: 未放置商品 */}
      {result.unplaced_items.length > 0 && (
        <div style={{
          ...cardStyle,
          borderColor: 'rgba(255,107,107,0.3)',
          background: 'rgba(255,107,107,0.06)',
        }}>
          <div style={{ fontSize: 12, color: 'var(--accent-red)', marginBottom: 8, fontWeight: 600 }}>
            <WarningOutlined /> 无法装入的商品
          </div>
          {result.unplaced_items.map((u, i) => (
            <div key={i} style={{ fontSize: 11, color: 'var(--text-primary)', padding: '2px 0' }}>
              {u.item_id} × {u.quantity}: <span style={{ color: 'var(--text-secondary)' }}>{u.reason}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
