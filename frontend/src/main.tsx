import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import enUS from 'antd/locale/en_US';
import { useTranslation } from 'react-i18next';
import App from './App';
import './i18n';
import './index.css';
import { useThemeStore } from './store/themeStore';

function getThemeConfig(mode: 'light' | 'dark') {
  return {
    token: {
      colorPrimary: '#4f6ef7',
      colorSuccess: '#52c41a',
      colorWarning: '#faad14',
      colorError: '#ff4d4f',
      colorInfo: '#4f6ef7',
      borderRadius: 6,
      fontSize: 14,
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif",
      ...(mode === 'light'
        ? {
            colorBgContainer: '#ffffff',
            colorBgLayout: '#f5f6fa',
            colorText: '#1a1d29',
            colorBorderSecondary: '#e8eaf0',
          }
        : {
            colorBgContainer: '#1a1d27',
            colorBgLayout: '#0f1117',
            colorBgElevated: '#242836',
            colorText: '#f0f2f5',
            colorTextSecondary: '#a8b0bd',
            colorTextTertiary: '#7d8590',
            colorBorder: '#3a4150',
            colorBorderSecondary: '#3a4150',
            colorFillSecondary: '#242836',
            colorFillTertiary: '#1a1d27',
          }),
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
  };
}

function ThemedApp() {
  const mode = useThemeStore((s) => s.mode);
  const { i18n } = useTranslation();
  const antdLocale = i18n.language?.startsWith('en') ? enUS : zhCN;
  return (
    <ConfigProvider locale={antdLocale} theme={getThemeConfig(mode)}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemedApp />
  </React.StrictMode>,
);
