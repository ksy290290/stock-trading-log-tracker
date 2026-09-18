import { Stack } from 'expo-router';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { SettingsProvider } from '../src/settings';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <SettingsProvider>
        <Stack>
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen name="trade/new" options={{ presentation: 'modal', title: '매매 기록 추가' }} />
          <Stack.Screen name="trade/[id]" options={{ presentation: 'modal', title: '매매 기록 수정' }} />
        </Stack>
      </SettingsProvider>
    </SafeAreaProvider>
  );
}
