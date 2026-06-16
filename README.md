import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Layers, Box, Play, RotateCcw } from 'lucide-react';
import { Switch, Button, Tooltip } from 'antd';
import PackageViewer3D from './PackageViewer3D';
import type { PackageOption } from '../services/api';
import './Package3DModal.css';

interface Package3DModalProps {
  visible: boolean;
  onClose: () => void;
  packageOption: PackageOption | null;
  itemSize: { length: number; width: number; height: number };
}

export default function Package3DModal({ 
  visible, 
  onClose, 
  packageOption, 
  itemSize 
}: Package3DModalProps) {
  const [isExploded, setIsExploded] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);
  const [explosionProgress, setExplosionProgress] = useState(0);
  const [assemblyProgress, setAssemblyProgress] = useState(1);
  const animationRef = useRef<number | null>(null);

  const resetToInitialState = useCallback(() => {
    setIsExploded(false);
    setExplosionProgress(0);
    setAssemblyProgress(1);
    setIsAnimating(false);
  }, []);

  useEffect(() => {
    if (visible) {
      resetToInitialState();
    }
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [visible, resetToInitialState]);

  const handleToggleView = useCallback(() => {
    if (isAnimating) return;
    
    if (!isExploded) {
      setIsExploded(true);
      setExplosionProgress(1);
      setAssemblyProgress(0);
    } else {
      setIsExploded(false);
      setExplosionProgress(0);
      setAssemblyProgress(1);
    }
  }, [isAnimating, isExploded]);

  const handleReset = useCallback(() => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }
    resetToInitialState();
  }, [resetToInitialState]);

  const handlePlayAnimation = useCallback(() => {
    if (isAnimating) return;
    
    setIsAnimating(true);
    setIsExploded(false);
    setExplosionProgress(0);
    setAssemblyProgress(1);
    
    const explosionDuration = 800;
    const assemblyDelay = 1000;
    const assemblyDuration = 2000;
    const startTime = performance.now();
    
    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      
      if (elapsed < explosionDuration) {
        const progress = elapsed / explosionDuration;
        const easeProgress = 1 - Math.pow(1 - progress, 3);
        setExplosionProgress(easeProgress);
        setIsExploded(true);
        setAssemblyProgress(0);
        animationRef.current = requestAnimationFrame(animate);
      } else if (elapsed < explosionDuration + assemblyDelay) {
        setExplosionProgress(1);
        setIsExploded(true);
        setAssemblyProgress(0);
        animationRef.current = requestAnimationFrame(animate);
      } else if (elapsed < explosionDuration + assemblyDelay + assemblyDuration) {
        const assemblyElapsed = elapsed - explosionDuration - assemblyDelay;
        const progress = assemblyElapsed / assemblyDuration;
        const easeProgress = 1 - Math.pow(1 - progress, 3);
        setIsExploded(false);
        setAssemblyProgress(easeProgress);
        animationRef.current = requestAnimationFrame(animate);
      } else {
        setIsExploded(false);
        setAssemblyProgress(1);
        setExplosionProgress(0);
        setIsAnimating(false);
      }
    };
    
    animationRef.current = requestAnimationFrame(animate);
  }, [isAnimating]);

  if (!packageOption) return null;

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="package-3d-modal-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="package-3d-modal"
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div className="modal-title">
                <Box size={20} />
                <span>包装方案 3D 预览</span>
              </div>
              <button className="modal-close-btn" onClick={onClose}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <div className="viewer-container">
                <PackageViewer3D
                  packageOption={packageOption}
                  itemSize={itemSize}
                  isExploded={isExploded}
                  explosionProgress={explosionProgress}
                  assemblyProgress={assemblyProgress}
                />
                
                <div className="viewer-controls">
                  <div className="control-group">
                    <Tooltip title={isExploded ? '切换到合并视图' : '切换到爆炸视图'}>
                      <div className="view-toggle">
                        <Layers size={16} />
                        <span>爆炸视图</span>
                        <Switch
                          checked={!isExploded}
                          onChange={handleToggleView}
                          disabled={isAnimating}
                          size="small"
                        />
                        <span>合并视图</span>
                      </div>
                    </Tooltip>
                  </div>
                  
                  <div className="control-actions">
                    <Tooltip title="播放装配动画">
                      <Button
                        type="primary"
                        icon={<Play size={14} />}
                        onClick={handlePlayAnimation}
                        disabled={isAnimating}
                        className="action-btn action-btn-primary"
                      >
                        播放动画
                      </Button>
                    </Tooltip>
                    <Tooltip title="重置视图">
                      <Button
                        icon={<RotateCcw size={14} />}
                        onClick={handleReset}
                        disabled={isAnimating}
                        className="action-btn action-btn-reset"
                      >
                        重置
                      </Button>
                    </Tooltip>
                  </div>
                </div>
              </div>

              <div className="info-panel">
                <div className="info-section">
                  <h4>包装信息</h4>
                  <div className="info-grid">
                    <div className="info-item">
                      <span className="info-label">单包件数</span>
                      <span className="info-value highlight">{packageOption.itemsPerPackage} 件</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">包装尺寸</span>
                      <span className="info-value">
                        {Math.round(packageOption.packageLength)}×{Math.round(packageOption.packageWidth)}×{Math.round(packageOption.packageHeight)} inch
                      </span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">包装重量</span>
                      <span className="info-value">{(packageOption.packageWeight / 1000).toFixed(2)} kg</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">单包费用</span>
                      <span className={`info-value ${packageOption.isOversized ? 'oversized' : ''}`}>
                        ${packageOption.totalFee.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="info-section">
                  <h4>商品规格</h4>
                  <div className="info-grid">
                    <div className="info-item">
                      <span className="info-label">商品尺寸</span>
                      <span className="info-value">{itemSize.length}×{itemSize.width}×{itemSize.height} inch</span>
                    </div>
                  </div>
                </div>

                <div className="info-section">
                  <h4>摆放方式</h4>
                  <div className="placement-info">
                    {(() => {
                      const countX = Math.floor(packageOption.packageLength / itemSize.length);
                      const countY = Math.floor(packageOption.packageHeight / itemSize.height);
                      const countZ = Math.floor(packageOption.packageWidth / itemSize.width);
                      return (
                        <div className="placement-detail">
                          <span className="placement-text">
                            长: {countX} 个 × 宽: {countZ} 个 × 高: {countY} 层
                          </span>
                          <span className="placement-total">
                            共计: {countX * countY * countZ} 个位置
                          </span>
                        </div>
                      );
                    })()}
                  </div>
                </div>

                {packageOption.chargeDetails && packageOption.chargeDetails.length > 0 && (
                  <div className="info-section">
                    <h4>费用明细</h4>
                    <ul className="charge-details">
                      {packageOption.chargeDetails.map((detail, index) => (
                        <li key={index}>{detail}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {packageOption.isOversized && (
                  <div className="oversized-warning-box">
                    <span className="warning-icon">⚠️</span>
                    <span>此包装方案会产生超尺寸附加费</span>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
