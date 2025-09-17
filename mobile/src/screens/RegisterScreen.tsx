import { useForm, Controller } from 'react-hook-form';
import { View, Text, TextInput, Pressable, StyleSheet } from 'react-native';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';

import api from '../api';

const schema = yup.object({
  full_name: yup.string().required('Ingresa tu nombre'),
  email: yup.string().email('Correo inválido').required('Requerido'),
  password: yup.string().min(8, 'Mínimo 8 caracteres').required('Requerido'),
  dob: yup.string().required('Fecha de nacimiento requerida')
});

interface Props {
  onLogin: () => void;
}

export default function RegisterScreen({ onLogin }: Props) {
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting }
  } = useForm({ resolver: yupResolver(schema) });

  const onSubmit = async (values: any) => {
    await api.post('/auth/register', values);
    onLogin();
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Crear cuenta</Text>
      <Controller
        control={control}
        name="full_name"
        defaultValue=""
        render={({ field: { onChange, value } }) => (
          <TextInput style={styles.input} placeholder="Nombre completo" value={value} onChangeText={onChange} />
        )}
      />
      {errors.full_name && <Text style={styles.error}>{errors.full_name.message}</Text>}
      <Controller
        control={control}
        name="email"
        defaultValue=""
        render={({ field: { onChange, value } }) => (
          <TextInput
            style={styles.input}
            placeholder="Correo"
            value={value}
            autoCapitalize="none"
            onChangeText={onChange}
          />
        )}
      />
      {errors.email && <Text style={styles.error}>{errors.email.message}</Text>}
      <Controller
        control={control}
        name="password"
        defaultValue=""
        render={({ field: { onChange, value } }) => (
          <TextInput style={styles.input} placeholder="Contraseña" secureTextEntry value={value} onChangeText={onChange} />
        )}
      />
      {errors.password && <Text style={styles.error}>{errors.password.message}</Text>}
      <Controller
        control={control}
        name="dob"
        defaultValue="1990-01-01"
        render={({ field: { onChange, value } }) => (
          <TextInput style={styles.input} placeholder="YYYY-MM-DD" value={value} onChangeText={onChange} />
        )}
      />
      {errors.dob && <Text style={styles.error}>{errors.dob.message}</Text>}
      <Pressable style={styles.button} onPress={handleSubmit(onSubmit)} disabled={isSubmitting}>
        <Text style={styles.buttonText}>{isSubmitting ? 'Creando...' : 'Registrarme'}</Text>
      </Pressable>
      <Pressable onPress={onLogin}>
        <Text style={styles.link}>¿Ya tienes cuenta? Inicia sesión</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    padding: 24,
    backgroundColor: '#0f172a'
  },
  title: {
    fontSize: 26,
    fontWeight: '700',
    color: '#fff',
    marginBottom: 16
  },
  input: {
    backgroundColor: '#fff',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    marginBottom: 12
  },
  button: {
    backgroundColor: '#22d3ee',
    padding: 14,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 8
  },
  buttonText: {
    color: '#0f172a',
    fontWeight: '700'
  },
  link: {
    color: '#f8fafc',
    marginTop: 16,
    textAlign: 'center'
  },
  error: {
    color: '#f87171',
    marginBottom: 4
  }
});
