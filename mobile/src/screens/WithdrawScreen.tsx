import { useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet } from 'react-native';

import api from '../api';

export default function WithdrawScreen({ onSuccess }: { onSuccess: () => void }) {
  const [amount, setAmount] = useState('100');
  const [alias, setAlias] = useState('CBU123');
  const [holder, setHolder] = useState('Mi Nombre');
  const [message, setMessage] = useState('');

  const submit = async () => {
    try {
      await api.post('/wallet/withdrawals', { amount, bank_alias: alias, bank_holder: holder });
      setMessage('Solicitud enviada. Recibirás la transferencia una vez aprobada.');
      onSuccess();
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'No se pudo solicitar el retiro');
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Solicitar retiro</Text>
      <TextInput style={styles.input} value={amount} onChangeText={setAmount} keyboardType="numeric" placeholder="Monto" />
      <TextInput style={styles.input} value={alias} onChangeText={setAlias} placeholder="Alias / CBU" />
      <TextInput style={styles.input} value={holder} onChangeText={setHolder} placeholder="Titular" />
      <Pressable style={styles.button} onPress={submit}>
        <Text style={styles.buttonText}>Solicitar</Text>
      </Pressable>
      {message && <Text style={styles.message}>{message}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
    padding: 24,
    gap: 12
  },
  title: {
    color: '#fff',
    fontSize: 26,
    fontWeight: '700'
  },
  input: {
    backgroundColor: '#1f2937',
    color: '#fff',
    borderRadius: 12,
    padding: 12
  },
  button: {
    backgroundColor: '#22d3ee',
    padding: 14,
    borderRadius: 12,
    alignItems: 'center'
  },
  buttonText: {
    color: '#0f172a',
    fontWeight: '700'
  },
  message: {
    color: '#cbd5f5',
    marginTop: 12
  }
});
