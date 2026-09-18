import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react';

import { createApiClient } from './api';

const BASE_URL_KEY = 'stockJournal.apiBaseUrl';
const API_KEY_KEY = 'stockJournal.apiKey';

interface SettingsState {
  baseUrl: string;
  apiKey: string;
  loaded: boolean;
  setBaseUrl: (value: string) => Promise<void>;
  setApiKey: (value: string) => Promise<void>;
}

const SettingsContext = createContext<SettingsState | undefined>(undefined);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [baseUrl, setBaseUrlState] = useState('');
  const [apiKey, setApiKeyState] = useState('');
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [storedUrl, storedKey] = await Promise.all([
          AsyncStorage.getItem(BASE_URL_KEY),
          AsyncStorage.getItem(API_KEY_KEY),
        ]);
        if (storedUrl) setBaseUrlState(storedUrl);
        if (storedKey) setApiKeyState(storedKey);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const setBaseUrl = async (value: string) => {
    setBaseUrlState(value);
    await AsyncStorage.setItem(BASE_URL_KEY, value);
  };

  const setApiKey = async (value: string) => {
    setApiKeyState(value);
    await AsyncStorage.setItem(API_KEY_KEY, value);
  };

  return (
    <SettingsContext.Provider value={{ baseUrl, apiKey, loaded, setBaseUrl, setApiKey }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider');
  return ctx;
}

export function useApiClient() {
  const { baseUrl, apiKey } = useSettings();
  return useMemo(() => createApiClient(baseUrl, apiKey), [baseUrl, apiKey]);
}
