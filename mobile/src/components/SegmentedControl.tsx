import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

interface Props<T extends string> {
  options: { label: string; value: T }[];
  value: T;
  onChange: (value: T) => void;
}

export function SegmentedControl<T extends string>({ options, value, onChange }: Props<T>) {
  return (
    <View style={styles.container}>
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <TouchableOpacity
            key={opt.value}
            style={[styles.segment, active && styles.segmentActive]}
            onPress={() => onChange(opt.value)}
          >
            <Text style={[styles.label, active && styles.labelActive]}>{opt.label}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    backgroundColor: '#eef0f3',
    borderRadius: 8,
    padding: 3,
  },
  segment: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 6,
    alignItems: 'center',
  },
  segmentActive: {
    backgroundColor: '#ffffff',
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 2,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  label: {
    fontSize: 14,
    color: '#6b7280',
    fontWeight: '500',
  },
  labelActive: {
    color: '#111827',
    fontWeight: '600',
  },
});
