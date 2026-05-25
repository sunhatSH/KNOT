import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#4f6ef7',
          colorSuccess: '#52c41a',
          colorWarning: '#faad14',
          colorError: '#ff4d4f',
          colorInfo: '#4f6ef7',
          borderRadius: 6,
          fontSize: 14,
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif",
          colorBgContainer: '#ffffff',
          colorBgLayout: '#f5f6fa',
          colorBorderSecondary: '#e8eaf0',
          boxShadow: 'none',
          boxShadowSecondary: 'none',
        },
        components: {
          Card: {
            paddingLG: 20,
            borderRadiusLG: 8,
            boxShadowTertiary: 'none',
          },
          Menu: {
            itemBg: 'transparent',
            horizontalItemSelectedColor: '#4f6ef7',
          },
          Button: {
            primaryShadow: 'none',
            borderRadius: 6,
          },
          Table: {
            borderRadiusLG: 8,
          },
          Modal: {
            borderRadiusLG: 8,
          },
        },
      }}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>,
);
