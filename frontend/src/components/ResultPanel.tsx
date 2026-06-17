import { Table, Tag, Empty, Button, Collapse, Tooltip, Progress } from 'antd';
import { DownloadOutlined, ExperimentOutlined } from '@ant-design/icons';
import type { OptimizeResponse, Placement, MultiOptimizeResponse } from '../types';

interface ResultPanelProps {
  result: OptimizeResponse | null;
  multiResult?: MultiOptimizeResponse | null;
  onSelectResult?: (result: OptimizeResponse) => void;
}

const SOLUTION_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  greedy: { label: '贪心', color: 'blue' },
  ga: { label: '遗传算法', color: 'green' },
  ls: { label: '局部搜索', color: 'cyan' },
  pareto: { label: '帕累托', color: 'orange' },
};

export default function ResultPanel({ result, multiResult, onSelectResult }: ResultPanelProps) {
  if (!result) {
    return (
      <Empty description="请配置商品并开始优化" style={{ padding: 40 }} />
    );
  }

  const handleExport = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'packing_result.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns = [
    { title: '商品', dataIndex: 'item_id', key: 'item_id', width: 70, fixed: 'left' as const },
    { title: '坐标 (X,Y,Z)', key: 'pos', width: 160,
      render: (_: any, r: Placement) =>
        `(${Math.round(r.x)}, ${Math.round(r.y)}, ${Math.round(r.z)})`,
    },
    { title: '尺寸 (L×W×H)', key: 'size', width: 150,
      render: (_: any, r: Placement) =>
        `${Math.round(r.length)}×${Math.round(r.width)}×${Math.round(r.height)}`,
    },
    { title: '旋转', dataIndex: 'rotation', key: 'rotation', width: 70 },
    { title: '朝向', dataIndex: 'orientation', key: 'orientation', width: 90 },
    { title: '易碎', key: 'fragile', width: 60,
      render: (_: any, r: Placement) =>
        r.is_fragile ? <Tag color="orange">易碎</Tag> : <span style={{ color: '#cbd5e1' }}>-</span>,
    },
  ];

  const typeInfo = SOLUTION_TYPE_LABELS[result.solution_type || 'greedy'];

  const feasibilityItems = result.feasibility_report ? [
    {
      key: 'feasibility',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ExperimentOutlined />
          可行性验证
          {result.feasibility_report.is_feasible ? (
            <Tag color="green">通过</Tag>
          ) : (
            <Tag color="red">失败</Tag>
          )}
        </span>
      ),
      children: (
        <div style={{ fontSize: 12, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <Tag color={result.feasibility_report.geometry_ok ? 'green' : 'red'}>
            几何 {result.feasibility_report.geometry_ok ? '✓' : '✗'}
          </Tag>
          <Tag color={result.feasibility_report.physics_ok ? 'green' : 'orange'}>
            物理 {result.feasibility_report.physics_ok ? '✓' : '!'}
          </Tag>
          <Tag color={result.feasibility_report.orientation_ok ? 'green' : 'orange'}>
            朝向 {result.feasibility_report.orientation_ok ? '✓' : '!'}
          </Tag>
          <Tooltip title="稳定性评分：评估装载方案的整体稳定性，值越高越稳定（范围 0-1）">
            <span style={{ color: '#64748b' }}>
              稳定性: <strong style={{ color: '#0f172a' }}>{result.feasibility_report.stability_score.toFixed(3)}</strong>
            </span>
          </Tooltip>
          <Tooltip title="支撑率：商品底部被其他商品或地面支撑的比例，值越高越稳固（范围 0-1）">
            <span style={{ color: '#64748b' }}>
              支撑率: <strong style={{ color: '#0f172a' }}>{result.feasibility_report.support_score.toFixed(3)}</strong>
            </span>
          </Tooltip>
          {result.feasibility_report.messages.length > 0 && (
            <div style={{ width: '100%', marginTop: 6, color: '#d97706' }}>
              {result.feasibility_report.messages.slice(0, 3).map((m, i) => (
                <div key={i}>· {m}</div>
              ))}
            </div>
          )}
        </div>
      ),
    },
  ] : [];

  return (
    <div>
      {/* 方案切换栏 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginBottom: 12,
        flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>优化结果</span>
          <Tag color={typeInfo?.color}>{typeInfo?.label}</Tag>
        </div>

        {/* 利用率进度条 */}
        <div style={{ display: 'flex', gap: 16, flex: 1, minWidth: 300 }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 }}>
              <span style={{ color: '#64748b' }}>空间利用率</span>
              <span style={{ fontWeight: 600, color: '#0f172a' }}>{(result.container_utilization * 100).toFixed(1)}%</span>
            </div>
            <Progress
              percent={Math.round(result.container_utilization * 100)}
              size="small"
              strokeColor={result.container_utilization >= 0.75 ? '#16a34a' : result.container_utilization >= 0.5 ? '#d97706' : '#dc2626'}
              showInfo={false}
            />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 }}>
              <span style={{ color: '#64748b' }}>载重利用率</span>
              <span style={{ fontWeight: 600, color: '#0f172a' }}>{(result.weight_utilization * 100).toFixed(1)}%</span>
            </div>
            <Progress
              percent={Math.round(result.weight_utilization * 100)}
              size="small"
              strokeColor={result.weight_utilization >= 0.75 ? '#16a34a' : result.weight_utilization >= 0.5 ? '#d97706' : '#dc2626'}
              showInfo={false}
            />
          </div>
        </div>

        <Button size="small" icon={<DownloadOutlined />} onClick={handleExport}>
          导出
        </Button>
      </div>

      {/* 指标标签栏 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Tag color="blue">已放置: {result.stats.total_items_placed}</Tag>
        <Tag color={result.unplaced_items.length > 0 ? 'red' : 'green'}>
          未放置: {result.stats.total_items_unplaced}
        </Tag>
        <Tag>耗时: {result.stats.algorithm_time_ms.toFixed(1)} ms</Tag>
        {result.cg_deviation_ratio !== undefined && (
          <Tooltip title="CG偏移：重心偏离集装箱中心的程度，越小越均衡（建议 < 15%）">
            <Tag color={result.cg_deviation_ratio < 0.15 ? 'green' : 'orange'}>
              CG偏移: {(result.cg_deviation_ratio * 100).toFixed(1)}%
            </Tag>
          </Tooltip>
        )}
        {result.metrics && (
          <>
            <Tooltip title="支撑率：所有商品平均底部支撑比例，越高越稳固（建议 ≥ 60%）">
              <Tag color={result.metrics.avg_support_ratio >= 0.6 ? 'green' : 'orange'}>
                支撑率: {(result.metrics.avg_support_ratio * 100).toFixed(0)}%
              </Tag>
            </Tooltip>
            {result.metrics.fragile_violations > 0 && (
              <Tag color="red">易碎品压迫: {result.metrics.fragile_violations}</Tag>
            )}
          </>
        )}
      </div>

      {/* 多方案切换 */}
      {multiResult && (
        <div style={{ marginBottom: 12, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#64748b' }}>方案切换：</span>
          <Tooltip title="贪心算法快速解">
            <Tag
              color={result === multiResult.primary ? 'blue' : 'default'}
              onClick={() => onSelectResult?.(multiResult.primary)}
              style={{ cursor: 'pointer' }}
            >
              贪心 ({(multiResult.primary.container_utilization * 100).toFixed(1)}%)
            </Tag>
          </Tooltip>
          {multiResult.ga_solution && (
            <Tooltip title="遗传算法优化">
              <Tag
                color={result === multiResult.ga_solution ? 'green' : 'default'}
                onClick={() => onSelectResult?.(multiResult.ga_solution!)}
                style={{ cursor: 'pointer' }}
              >
                GA ({(multiResult.ga_solution.container_utilization * 100).toFixed(1)}%)
              </Tag>
            </Tooltip>
          )}
          {multiResult.ls_solution && (
            <Tooltip title="局部搜索优化">
              <Tag
                color={result === multiResult.ls_solution ? 'cyan' : 'default'}
                onClick={() => onSelectResult?.(multiResult.ls_solution!)}
                style={{ cursor: 'pointer' }}
              >
                LS ({(multiResult.ls_solution.container_utilization * 100).toFixed(1)}%)
              </Tag>
            </Tooltip>
          )}
          {multiResult.pareto_solutions?.map((p, i) => (
            <Tooltip key={i} title={`帕累托方案 #${i + 1}`}>
              <Tag
                color={result === p ? 'orange' : 'default'}
                onClick={() => onSelectResult?.(p)}
                style={{ cursor: 'pointer' }}
              >
                P{i + 1} ({(p.container_utilization * 100).toFixed(1)}%)
              </Tag>
            </Tooltip>
          ))}
        </div>
      )}

      {/* 未放置商品警告 */}
      {result.unplaced_items.length > 0 && (
        <div
          style={{
            marginBottom: 12,
            padding: '10px 12px',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: 8,
            fontSize: 12,
          }}
        >
          <strong style={{ color: '#dc2626' }}>无法装入的商品：</strong>
          <div style={{ marginTop: 4, color: '#7f1d1d' }}>
            {result.unplaced_items.map((u, i) => (
              <div key={i}>
                {u.item_id} × {u.quantity}: {u.reason}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 可行性验证折叠面板 */}
      {feasibilityItems.length > 0 && (
        <Collapse
          items={feasibilityItems}
          size="small"
          defaultActiveKey={[]}
          style={{ marginBottom: 12 }}
        />
      )}

      {/* 装配明细表格 */}
      <Table
        dataSource={result.placements}
        columns={columns}
        rowKey={(_, i) => String(i ?? 0)}
        pagination={false}
        size="small"
        scroll={{ y: 130, x: 'max-content' }}
      />
    </div>
  );
}
