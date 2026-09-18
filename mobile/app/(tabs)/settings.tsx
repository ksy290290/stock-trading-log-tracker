import { useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import { createApiClient } from '../../src/api';
import { useSettings } from '../../src/settings';

export default function SettingsScreen() {
  const { baseUrl, apiKey, setBaseUrl, setApiKey } = useSettings();
  const [urlInput, setUrlInput] = useState(baseUrl);
  const [keyInput, setKeyInput] = useState(apiKey);
  const [testing, setTesting] = useState(false);

  const handleSave = async () => {
    await setBaseUrl(urlInput.trim());
    await setApiKey(keyInput.trim());
    Alert.alert('저장됨', 'API 서버 설정이 저장되었습니다.');
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const client = createApiClient(urlInput.trim(), keyInput.trim());
      const res = await client.health();
      Alert.alert('연결 성공', `서버 응답: ${res.status}`);
    } catch (e) {
      Alert.alert('연결 실패', e instanceof Error ? e.message : String(e));
    } finally {
      setTesting(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>API 서버 연결</Text>
        <Text style={styles.description}>
          매매일지 데이터를 가져올 API 서버 주소를 입력하세요. 리포지토리의 api_server.py를
          배포한 뒤(Render, Fly.io 등) 그 주소를 넣으면 됩니다.
        </Text>

        <Text style={styles.label}>서버 주소</Text>
        <TextInput
          style={styles.input}
          value={urlInput}
          onChangeText={setUrlInput}
          placeholder="https://your-api.onrender.com"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />

        <Text style={styles.label}>API Key (선택, 서버에 API_KEY 설정한 경우)</Text>
        <TextInput
          style={styles.input}
          value={keyInput}
          onChangeText={setKeyInput}
          placeholder="비워두면 인증 없이 요청"
          autoCapitalize="none"
          autoCorrect={false}
          secureTextEntry
        />

        <TouchableOpacity style={styles.primaryButton} onPress={handleSave}>
          <Text style={styles.primaryLabel}>저장</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.secondaryButton} onPress={handleTest} disabled={testing}>
          <Text style={styles.secondaryLabel}>{testing ? '연결 확인 중...' : '연결 테스트'}</Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20, gap: 4 },
  title: { fontSize: 18, fontWeight: '700', color: '#111827', marginBottom: 6 },
  description: { fontSize: 13, color: '#6b7280', marginBottom: 20, lineHeight: 19 },
  label: { fontSize: 13, color: '#6b7280', marginBottom: 6, marginTop: 14, fontWeight: '500' },
  input: {
    borderWidth: 1,
    borderColor: '#d1d5db',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: '#fff',
  },
  primaryButton: {
    backgroundColor: '#2563eb',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 24,
  },
  primaryLabel: { color: '#fff', fontSize: 16, fontWeight: '600' },
  secondaryButton: {
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 10,
    borderWidth: 1,
    borderColor: '#d1d5db',
  },
  secondaryLabel: { color: '#374151', fontSize: 15, fontWeight: '600' },
});
