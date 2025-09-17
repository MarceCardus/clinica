import { useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, Image } from 'react-native';
import * as ImagePicker from 'expo-image-picker';

import api from '../api';

export default function TopUpScreen({ onSuccess }: { onSuccess: () => void }) {
  const [amount, setAmount] = useState('100');
  const [bankName, setBankName] = useState('Banco Demo');
  const [refNumber, setRefNumber] = useState('REF123');
  const [proof, setProof] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [status, setStatus] = useState<string>('');

  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.All });
    if (!result.canceled) {
      setProof(result.assets[0]);
    }
  };

  const submit = async () => {
    if (!proof) {
      setStatus('Selecciona un comprobante');
      return;
    }
    const form = new FormData();
    form.append('amount', amount);
    form.append('bank_name', bankName);
    form.append('ref_number', refNumber);
    form.append('proof', {
      uri: proof.uri,
      name: proof.fileName || 'comprobante.jpg',
      type: proof.mimeType || 'image/jpeg'
    } as any);
    await api.post('/wallet/topups', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    setStatus('Recarga enviada, pendiente de aprobación');
    onSuccess();
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Solicitar recarga</Text>
      <TextInput style={styles.input} value={amount} onChangeText={setAmount} keyboardType="numeric" placeholder="Monto" />
      <TextInput style={styles.input} value={bankName} onChangeText={setBankName} placeholder="Banco" />
      <TextInput style={styles.input} value={refNumber} onChangeText={setRefNumber} placeholder="Referencia" />
      {proof && <Image source={{ uri: proof.uri }} style={styles.preview} />}
      <Pressable style={styles.buttonSecondary} onPress={pickImage}>
        <Text style={styles.buttonSecondaryText}>{proof ? 'Cambiar archivo' : 'Adjuntar comprobante'}</Text>
      </Pressable>
      <Pressable style={styles.button} onPress={submit}>
        <Text style={styles.buttonText}>Enviar solicitud</Text>
      </Pressable>
      {status && <Text style={styles.status}>{status}</Text>}
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
    fontSize: 24,
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
  buttonSecondary: {
    borderColor: '#38bdf8',
    borderWidth: 1,
    padding: 12,
    borderRadius: 12,
    alignItems: 'center'
  },
  buttonSecondaryText: {
    color: '#38bdf8',
    fontWeight: '600'
  },
  preview: {
    width: '100%',
    height: 160,
    borderRadius: 12,
    marginTop: 8
  },
  status: {
    color: '#cbd5f5',
    marginTop: 8
  }
});
