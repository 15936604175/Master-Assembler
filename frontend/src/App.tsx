import { useState } from 'react';
import { ConfigProvider } from 'antd';
import InputPage from './pages/InputPage';
import ResultPage from './pages/ResultPage';
import type { OptimizeResponse, ContainerConfig, MultiOptimizeResponse } from './types';
import type { ItemRow } from './components/ItemListEditor';
import './App.css';

type Algorithm = 'greedy' | 'phase2';

export default function App() {
  const [currentPage, setCurrentPage] = useState<'input' | 'result'>('input');
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [multiResult, setMultiResult] = useState<MultiOptimizeResponse | null>(null);
  const [container, setContainer] = useState<ContainerConfig>({
    length: 5898, width: 2352, height: 2395, max_weight: 28000,
  });
  const [items, setItems] = useState<ItemRow[]>([]);
  const [algorithm, setAlgorithm] = useState<Algorithm>('phase2');

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
          colorPrimary: '#1d4ed8',
          colorSuccess: '#16a34a',
          colorWarning: '#d97706',
          colorError: '#dc2626',
          colorInfo: '#2563eb',
          borderRadius: 8,
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
          fontSize: 14,
          controlHeight: 36,
          wireframe: false,
        },
        components: {
          Card: {
            borderRadiusLG: 10,
            boxShadowTertiary: '0 1px 3px rgba(0,0,0,0.06)',
            headerFontSize: 15,
            headerHeight: 44,
          },
          Button: {
            borderRadius: 8,
            controlHeight: 36,
            controlHeightLG: 44,
            fontWeight: 500,
          },
          Table: {
            headerBg: '#f8fafc',
            headerColor: '#475569',
            headerSplitColor: '#e2e8f0',
            rowHoverBg: '#f1f5f9',
            borderColor: '#e2e8f0',
            cellPaddingBlock: 10,
            cellPaddingInline: 12,
          },
          Input: {
            borderRadius: 8,
            controlHeight: 36,
            activeShadow: '0 0 0 2px rgba(29, 78, 216, 0.12)',
          },
          InputNumber: {
            borderRadius: 8,
            controlHeight: 36,
          },
          Select: {
            borderRadius: 8,
            controlHeight: 36,
          },
          Tag: {
            borderRadiusSM: 4,
          },
          Radio: {
            colorPrimary: '#1d4ed8',
          },
        },
      }}
    >
      {currentPage === 'input' ? (
        <InputPage
          onOptimizeComplete={handleOptimizeComplete}
          container={container}
          setContainer={setContainer}
          items={items}
          setItems={setItems}
          algorithm={algorithm}
          setAlgorithm={setAlgorithm}
          existingResult={result}
          existingMultiResult={multiResult}
        />
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
