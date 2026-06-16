import { Card, Table, Tag, Empty, Button, Collapse, Tooltip } from 'antd';
import { DownloadOutlined, ExperimentOutlined } from '@ant-design/icons';
import UtilizationBar from './UtilizationBar';
import type { OptimizeResponse, Placement, MultiOptimizeResponse } from '../types';

interface ResultPanelProps {
  result: OptimizeResponse | null;
  multiResult?: MultiOptimizeResponse | null;
  onSelectResult?: (result: OptimizeResponse) => void;
}

const SOLUTION_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  greedy: { label: '贪心', color: 'blue' },
  ga: { label: '遗传算法', color: 'green' },
  ls: { label: '局部搜索', color: 'purple' },
  pareto: { label: '帕累托', color: 'orange' },
};

export default function ResultPanel({ result, multiResult, onSelectResult }: ResultPanelProps) {
  if (!result) {
    return (
      <Card title="优化结果" size="small" style={{ height: '100%' }}>
        <Empty description="请配置商品并开始优化" />
      </Card>
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
    { title: '商品', dataIndex: 'item_id', key: 'item_id', width: 70 },
    { title: '坐标 (X,Y,Z)', key: 'pos', width: 150,
      render: (_: any, r: Placement) =>
        `(${Math.round(r.x)}, ${Math.round(r.y)}, ${Math.round(r.z)})`,
    },
    { title: '尺寸 (L×W×H)', key: 'size', width: 145,
      render: (_: any, r: Placement) =>
        `${Math.round(r.length)}×${Math.round(r.width)}×${Math.round(r.height)}`,
    },
    { title: '旋转', dataIndex: 'rotation', key: 'rotation', width: 70 },
    { title: '朝向', dataIndex: 'orientation', key: 'orientation', width: 90 },
    { title: '易碎', key: 'fragile', width: 50,
      render: (_: any, r: Placement) => (r.is_fragile ? '⚠' : ''),
    },
  ];

  const typeInfo = SOLUTION_TYPE_LABELS[result.solution_type || 'greedy'];

  const feasibilityItems = result.feasibility_report ? [
    {
      key: 'feasibility',
      label: (
        <span>
          <ExperimentOutlined style={{ marginRight: 6 }} />
          可行性验证
          {result.feasibility_report.is_feasible ? (
            <Tag color="green" style={{ marginLeft: 8 }}>通过</Tag>
          ) : (
            <Tag color="red" style={{ marginLeft: 8 }}>失败</Tag>
          )}
        </span>
      ),
      children: (
        <div style={{ fontSize: 12 }}>
          <Tag color={result.feasibility_report.geometry_ok ? 'green' : 'red'}>
            几何 {result.feasibility_report.geometry_ok ? '✓' : '✗'}
          </Tag>
          <Tag color={result.feasibility_report.physics_ok ? 'green' : 'orange'}>
            物理 {result.feasibility_report.physics_ok ? '✓' : '!'}
          </Tag>
          <Tag color={result.feasibility_report.orientation_ok ? 'green' : 'orange'}>
            朝向 {result.feasibility_report.orientation_ok ? '✓' : '!'}
          </Tag>
          <div style={{ marginTop: 6 }}>
            <span>稳定性: </span>
            <Tag color="blue">{result.feasibility_report.stability_score.toFixed(3)}</Tag>
            <span>  支撑率: </span>
            <Tag color="cyan">{result.feasibility_report.support_score.toFixed(3)}</Tag>
          </div>
          {result.feasibility_report.messages.length > 0 && (
            <div style={{ marginTop: 6, color: '#faad14' }}>
              {result.feasibility_report.messages.slice(0, 3).map((m, i) => (
                <div key={i}>{m}</div>
              ))}
            </div>
          )}
        </div>
      ),
    },
  ] : [];

  return (
    <Card
      title={
        <span>
          优化结果
          <Tag color={typeInfo?.color} style={{ marginLeft: 8 }}>
            {typeInfo?.label}
          </Tag>
        </span>
      }
      size="small"
      extra={
        <Button size="small" icon={<DownloadOutlined />} onClick={handleExport}>
          导出
        </Button>
      }
      style={{ height: '100%', overflow: 'auto' }}
    >
      <UtilizationBar
        spaceUtil={result.container_utilization}
        weightUtil={result.weight_utilization}
        totalWeight={result.total_weight}
      />

      <div style={{ margin: '8px 0' }}>
        <Tag color="blue">已放置: {result.stats.total_items_placed}</Tag>
        <Tag color={result.unplaced_items.length > 0 ? 'red' : 'green'}>
          未放置: {result.stats.total_items_unplaced}
        </Tag>
        <Tag>耗时: {result.stats.algorithm_time_ms.toFixed(1)} ms</Tag>
        {result.cg_deviation_ratio !== undefined && (
          <Tag color={result.cg_deviation_ratio < 0.15 ? 'green' : 'orange'}>
            CG偏移: {(result.cg_deviation_ratio * 100).toFixed(1)}%
          </Tag>
        )}
        {result.metrics && (
          <>
            <Tag color={result.metrics.avg_support_ratio >= 0.6 ? 'green' : 'orange'}>
              支撑率: {(result.metrics.avg_support_ratio * 100).toFixed(0)}%
            </Tag>
            {result.metrics.fragile_violations > 0 && (
              <Tag color="red">
                易碎品压迫: {result.metrics.fragile_violations}
              </Tag>
            )}
          </>
        )}
      </div>

      {multiResult && (
        <div style={{ margin: '8px 0', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: '#888' }}>方案切换：</span>
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
                color={result === multiResult.ls_solution ? 'purple' : 'default'}
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
                P${i + 1} ({(p.container_utilization * 100).toFixed(1)}%)
              </Tag>
            </Tooltip>
          ))}
        </div>
      )}

      {result.unplaced_items.length > 0 && (
        <div
          style={{
            marginBottom: 8,
            padding: 8,
            background: '#fff2f0',
            border: '1px solid #ffccc7',
            borderRadius: 4,
          }}
        >
          <strong>⚠ 无法装入的商品：</strong>
          {result.unplaced_items.map((u, i) => (
            <div key={i}>
              {u.item_id} × {u.quantity}: {u.reason}
            </div>
          ))}
        </div>
      )}

      <Collapse
        items={feasibilityItems}
        size="small"
        defaultActiveKey={[]}
        style={{ marginBottom: 8 }}
      />

      <Table
        dataSource={result.placements}
        columns={columns}
        rowKey={(_, i) => String(i ?? 0)}
        pagination={false}
        size="small"
        scroll={{ y: 130 }}
      />
    </Card>
  );
}
