import { useState } from 'react';
import { Layout, ConfigProvider } from 'antd';
import ControlPanel from './components/ControlPanel';
import Layout3D from './components/Layout3D';
import ResultPanel from './components/ResultPanel';
import type { OptimizeResponse, ContainerConfig, MultiOptimizeResponse } from './types';
import './App.css';

const { Sider, Content } = Layout;

export default function App() {
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [multiResult, setMultiResult] = useState<MultiOptimizeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [container] = useState<ContainerConfig>({
    length: 5898, width: 2352, height: 2395, max_weight: 28000,
  });

  const handleResult = (res: OptimizeResponse) => {
    setResult(res);
  };

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1677ff',
        },
      }}
    >
      <Layout style={{ height: '100vh' }}>
        <Sider
          width={420}
          style={{
            background: '#fff',
            overflow: 'auto',
            padding: 16,
            borderRight: '1px solid #f0f0f0',
          }}
        >
          <ControlPanel
            onResult={handleResult}
            onMultiResult={setMultiResult}
            onLoading={setLoading}
          />
        </Sider>
        <Layout>
          <Content style={{ position: 'relative', display: 'flex', flexDirection: 'column' }}>
            {loading && (
              <div
                style={{
                  position: 'absolute',
                  top: 16,
                  left: '50%',
                  transform: 'translateX(-50%)',
                  zIndex: 10,
                  padding: '8px 24px',
                  background: '#1677ff',
                  color: '#fff',
                  borderRadius: 6,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                }}
              >
                优化计算中...
              </div>
            )}
            <div style={{ flex: 1, minHeight: 0 }}>
              <Layout3D result={result} container={container} />
            </div>
            <div style={{ height: 280, padding: 12, borderTop: '1px solid #f0f0f0' }}>
              <ResultPanel result={result} multiResult={multiResult} onSelectResult={setResult} />
            </div>
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
}
