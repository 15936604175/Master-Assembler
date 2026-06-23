import { useRef, useEffect, useMemo } from 'react';
import { COLORS } from './PlacedItem';
import type { OptimizeResponse, ContainerConfig, Placement } from '../types';

interface Layout2DProps {
  result: OptimizeResponse | null;
  container: ContainerConfig;
}

/** 2D 俯视图 - 绘制每个放置物品在 XZ 平面的投影 */
export default function Layout2D({ result, container }: Layout2DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // 为每个 item_id 分配颜色
  const itemColors = useMemo(() => {
    const colorMap: Record<string, string> = {};
    if (result) {
      const ids = [...new Set(result.placements.map((p) => p.item_id))];
      ids.forEach((id, i) => { colorMap[id] = COLORS[i % COLORS.length]; });
    }
    return colorMap;
  }, [result]);

  const itemIds = useMemo(() => {
    if (!result) return [];
    return [...new Set(result.placements.map((p) => p.item_id))];
  }, [result]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrapper = wrapperRef.current;
    if (!canvas || !wrapper) return;

    const resizeObserver = new ResizeObserver(() => {
      draw(canvas, wrapper.clientWidth, wrapper.clientHeight);
    });
    resizeObserver.observe(wrapper);

    draw(canvas, wrapper.clientWidth, wrapper.clientHeight);

    return () => resizeObserver.disconnect();
  }, [result, container, itemColors]);

  function draw(canvas: HTMLCanvasElement, w: number, h: number) {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    // 背景
    ctx.fillStyle = '#2B2B2B';
    ctx.fillRect(0, 0, w, h);

    const padding = 50;
    const availW = w - padding * 2;
    const availH = h - padding * 2;

    // 计算缩放比例 (容器 XZ 平面: length × width)
    const scaleX = availW / container.length;
    const scaleZ = availH / container.width;
    const scale = Math.min(scaleX, scaleZ);

    const ox = padding + (availW - container.length * scale) / 2;
    const oz = padding + (availH - container.width * scale) / 2;

    // 绘制网格
    ctx.strokeStyle = '#3A3A3A';
    ctx.lineWidth = 0.5;
    const gridSize = Math.max(container.length, container.width) / 10;
    for (let x = 0; x <= container.length; x += gridSize) {
      const px = ox + x * scale;
      ctx.beginPath(); ctx.moveTo(px, oz); ctx.lineTo(px, oz + container.width * scale); ctx.stroke();
    }
    for (let z = 0; z <= container.width; z += gridSize) {
      const pz = oz + z * scale;
      ctx.beginPath(); ctx.moveTo(ox, pz); ctx.lineTo(ox + container.length * scale, pz); ctx.stroke();
    }

    // 绘制容器边框
    ctx.strokeStyle = '#666';
    ctx.lineWidth = 2;
    ctx.strokeRect(ox, oz, container.length * scale, container.width * scale);

    // 容器尺寸标注（避开中线）
    ctx.fillStyle = '#888';
    ctx.font = '11px Consolas, monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`${container.length}mm`, ox + container.length * scale - 70, oz - 8);
    ctx.save();
    ctx.translate(ox - 10, oz + 12);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(`${container.width}mm`, 0, 0);
    ctx.restore();

    // 绘制中线（虚线，超出容器边界）
    const cx = ox + container.length * scale / 2;
    const cz = oz + container.width * scale / 2;
    const extend = 16;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 6]);
    // X 方向中线（长度方向）
    ctx.beginPath(); ctx.moveTo(ox - extend, cz); ctx.lineTo(ox + container.length * scale + extend, cz); ctx.stroke();
    // Z 方向中线（宽度方向）
    ctx.beginPath(); ctx.moveTo(cx, oz - extend); ctx.lineTo(cx, oz + container.width * scale + extend); ctx.stroke();
    ctx.setLineDash([]);

    if (!result) {
      // 空状态
      ctx.fillStyle = '#666';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('暂无装配方案，请在左侧配置并计算', w / 2, h / 2);
      return;
    }

    // 按 Y 坐标分层绘制（从底到顶），使上层物品覆盖下层
    const sorted = [...result.placements].sort((a, b) => a.y - b.y);

    sorted.forEach((p: Placement) => {
      const px = ox + p.x * scale;
      const pz = oz + p.z * scale;
      const pw = p.length * scale;
      const ph = p.width * scale;

      const color = itemColors[p.item_id] || '#888';

      // 填充
      ctx.globalAlpha = 0.65;
      ctx.fillStyle = color;
      ctx.fillRect(px, pz, pw, ph);

      // 边框
      ctx.globalAlpha = 1;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(px, pz, pw, ph);

      // 标签（如果矩形够大）
      if (pw > 20 && ph > 14) {
        ctx.fillStyle = '#fff';
        ctx.font = `bold ${Math.min(11, Math.max(8, Math.min(pw, ph) * 0.35))}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.shadowColor = 'rgba(0,0,0,0.7)';
        ctx.shadowBlur = 3;
        ctx.fillText(p.item_id, px + pw / 2, pz + ph / 2);
        ctx.shadowBlur = 0;
      }
    });

    // 重心标记
    if (result.center_of_gravity) {
      const cgx = ox + result.center_of_gravity.x * scale;
      const cgz = oz + result.center_of_gravity.z * scale;

      // 外圈发光
      const grad = ctx.createRadialGradient(cgx, cgz, 0, cgx, cgz, 28);
      grad.addColorStop(0, 'rgba(255,107,107,0.4)');
      grad.addColorStop(1, 'rgba(255,107,107,0)');
      ctx.fillStyle = grad;
      ctx.beginPath(); ctx.arc(cgx, cgz, 28, 0, Math.PI * 2); ctx.fill();

      // 十字线（加粗加亮）
      ctx.strokeStyle = '#FF4444';
      ctx.lineWidth = 3;
      const crossSize = 12;
      ctx.shadowColor = 'rgba(255,68,68,0.6)';
      ctx.shadowBlur = 8;
      ctx.beginPath(); ctx.moveTo(cgx - crossSize, cgz); ctx.lineTo(cgx + crossSize, cgz); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cgx, cgz - crossSize); ctx.lineTo(cgx, cgz + crossSize); ctx.stroke();

      // 中心圆点
      ctx.fillStyle = '#FF4444';
      ctx.beginPath(); ctx.arc(cgx, cgz, 4, 0, Math.PI * 2); ctx.fill();
      ctx.shadowBlur = 0;

      // CG 标签（带背景）
      const label = 'CG';
      ctx.font = 'bold 12px sans-serif';
      const labelW = ctx.measureText(label).width;
      const lx = cgx + 14, ly = cgz - 10;
      ctx.fillStyle = 'rgba(30,30,36,0.85)';
      ctx.fillRect(lx - 4, ly - 10, labelW + 8, 18);
      ctx.strokeStyle = '#FF4444';
      ctx.lineWidth = 1;
      ctx.strokeRect(lx - 4, ly - 10, labelW + 8, 18);
      ctx.fillStyle = '#FF4444';
      ctx.textAlign = 'left';
      ctx.fillText(label, lx, ly + 2);
    }

    // 图例
    const legendX = w - 140;
    let legendY = 20;
    ctx.fillStyle = 'rgba(37,37,46,0.9)';
    ctx.fillRect(legendX - 10, legendY - 5, 140, itemIds.length * 20 + 25);
    ctx.strokeStyle = '#3E3E42';
    ctx.lineWidth = 1;
    ctx.strokeRect(legendX - 10, legendY - 5, 140, itemIds.length * 20 + 25);

    ctx.fillStyle = '#A0A0A0';
    ctx.font = 'bold 11px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('商品图例', legendX, legendY + 10);
    legendY += 20;

    itemIds.forEach((id, i) => {
      ctx.fillStyle = COLORS[i % COLORS.length];
      ctx.fillRect(legendX, legendY, 12, 12);
      ctx.fillStyle = '#E0E0E0';
      ctx.font = '11px sans-serif';
      ctx.fillText(id, legendX + 18, legendY + 10);
      legendY += 18;
    });
  }

  return (
    <div ref={wrapperRef} style={{
      width: '100%', height: '100%',
      background: 'var(--viewport-bg)', position: 'relative',
    }}>
      <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />
    </div>
  );
}
