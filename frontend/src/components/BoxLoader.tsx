import './BoxLoader.css';

interface BoxLoaderProps {
  text?: string;
}

/**
 * 3D 方块装载动画（源自 style.md）
 * 用于优化计算等待时展示
 */
export default function BoxLoader({ text = '正在优化装配方案...' }: BoxLoaderProps) {
  return (
    <div className="box-loader-wrapper">
      <div className="box-loader">
        <div className="box box0"><div /></div>
        <div className="box box1"><div /></div>
        <div className="box box2"><div /></div>
        <div className="box box3"><div /></div>
        <div className="box box4"><div /></div>
        <div className="box box5"><div /></div>
        <div className="box box6"><div /></div>
        <div className="box box7"><div /></div>
        <div className="ground"><div /></div>
      </div>
      <div className="box-loader-text">{text}</div>
    </div>
  );
}
