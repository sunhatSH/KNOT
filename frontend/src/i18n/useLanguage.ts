import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';

export function useLanguage() {
  const { i18n } = useTranslation();

  const currentLang = i18n.language?.startsWith('en') ? 'en' : 'zh';

  const switchLanguage = useCallback((lang: 'zh' | 'en') => {
    i18n.changeLanguage(lang);
  }, [i18n]);

  return { currentLang, switchLanguage } as const;
}
