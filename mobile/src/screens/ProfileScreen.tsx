import { useEffect, useState } from 'react';
import { View, Text, TextInput, StyleSheet, Pressable } from 'react-native';

import api from '../api';

interface KYC {
  doc_type?: string;
  doc_number?: string;
  doc_image_url?: string;
  verified_bool?: boolean;
}

export default function ProfileScreen() {
  const [kyc, setKyc] = useState<KYC>({});
  const [docType, setDocType] = useState('DNI');
  const [docNumber, setDocNumber] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    api.get<KYC>('/kyc/me').then((resp) => {
      setKyc(resp.data);
      setDocType(resp.data.doc_type || 'DNI');
      setDocNumber(resp.data.doc_number || '');
    });
  }, []);

  const update = async () => {
    await api.put('/kyc/me', { doc_type: docType, doc_number: docNumber });
    setMessage('Datos actualizados');
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Perfil</Text>
      <Text style={styles.paragraph}>Estado de verificación: {kyc.verified_bool ? 'Verificado' : 'Pendiente'}</Text>
      <TextInput style={styles.input} value={docType} onChangeText={setDocType} placeholder="Tipo de documento" />
      <TextInput style={styles.input} value={docNumber} onChangeText={setDocNumber} placeholder="Número" />
      <Pressable style={styles.button} onPress={update}>
        <Text style={styles.buttonText}>Guardar</Text>
      </Pressable>
      <Text style={styles.legalTitle}>Aviso legal</Text>
      <Text style={styles.paragraph}>
        Solo mayores de 18 años. El saldo virtual representa montos transferidos y verificados. Las apuestas se
        cierran 10 minutos antes del partido. Los pagos de retiros se realizan por transferencia bancaria al titular
        validado.
      </Text>
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
    backgroundColor: '#38bdf8',
    padding: 14,
    borderRadius: 12,
    alignItems: 'center'
  },
  buttonText: {
    color: '#0f172a',
    fontWeight: '700'
  },
  paragraph: {
    color: '#cbd5f5'
  },
  legalTitle: {
    color: '#22d3ee',
    fontWeight: '600',
    marginTop: 12
  },
  message: {
    color: '#cbd5f5',
    marginTop: 12
  }
});
