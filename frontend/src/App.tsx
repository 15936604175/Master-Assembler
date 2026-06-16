import { useState } from 'react';
import { ConfigProvider } from 'antd';
import InputPage from './pages/InputPage';
import ResultPage from './pages/ResultPage';
import type { OptimizeResponse, ContainerConfig, MultiOptimizeResponse } from './types';
import './App.css';

export default function App() {
  const [currentPage, setCurrentPage] = useState<'input' | 'result'>('input');
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [multiResult, setMultiResult] = useState<MultiOptimizeResponse | null>(null);
  const [container, setContainer] = useState<ContainerConfig>({
    length: 5898, width: 2352, height: 2395, max_weight: 28000,
  });

  const handleOptimizeComplete = (
    optimizeResult: OptimizeResponse,
    multiOptimizeResult?: MultiOptimizeResponse | null,
    containerConfig?: ContainerConfig
  ) => {
    setResult(optimizeResult);
    setMultiResult(multiOptimizeResult || null);
    if (containerConfig) {
      setContainer(containerConfig);
    }
    setCurrentPage('result');
  };

  const handleBack = () => {
    setCurrentPage('input');
  };

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1677ff',
        },
      }}
    >
      {currentPage === 'input' ? (
        <InputPage onOptimizeComplete={handleOptimizeComplete} />
      ) : (
        result && (
          <ResultPage
            result={result}
            multiResult={multiResult}
            container={container}
            onBack={handleBack}
          />
        )
      )}
    </ConfigProvider>
  );
}