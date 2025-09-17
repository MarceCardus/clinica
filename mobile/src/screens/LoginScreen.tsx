import { useForm, Controller } from 'react-hook-form';
import { View, Text, TextInput, Pressable, StyleSheet } from 'react-native';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';

import api from '../api';
import { useAuthStore } from '../store/useAuth';

const schema = yup.object({
  email: yup.string().email('Correo inválido').required('Requerido'),
  password: yup.string().min(8, 'Mínimo 8 caracteres').required('Requerido')
});

interface Props {
  onRegister: () => void;
  onSuccess: () => void;
}

export default function LoginScreen({ onRegister, onSuccess }: Props) {
  const setAuth = useAuthStore((s) => s.setAuth);
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting }
  } = useForm({ resolver: yupResolver(schema) });
  const onSubmit = async (values: any) => {
    const response = await api.post('/auth/login', values);
    setAuth(response.data.access_token, values.email);
    onSuccess();
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Bienvenido</Text>
      <Text style={styles.subtitle}>Ingresa a tu cuenta para apostar en los torneos internos.</Text>
      <Controller
        control={control}
        name="email"
        defaultValue=""
        render={({ field: { onChange, value } }) => (
          <TextInput
            style={styles.input}
            placeholder="Correo"
            autoCapitalize="none"
            keyboardType="email-address"
            value={value}
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
          <TextInput
            style={styles.input}
            placeholder="Contraseña"
            secureTextEntry
            value={value}
            onChangeText={onChange}
          />
        )}
      />
      {errors.password && <Text style={styles.error}>{errors.password.message}</Text>}
      <Pressable style={styles.button} onPress={handleSubmit(onSubmit)} disabled={isSubmitting}>
        <Text style={styles.buttonText}>{isSubmitting ? 'Ingresando...' : 'Ingresar'}</Text>
      </Pressable>
      <Pressable onPress={onRegister}>
        <Text style={styles.link}>¿No tienes cuenta? Regístrate</Text>
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
    fontSize: 28,
    fontWeight: '700',
    color: '#fff',
    marginBottom: 8
  },
  subtitle: {
    color: '#cbd5f5',
    marginBottom: 24
  },
  input: {
    backgroundColor: '#fff',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    marginBottom: 12
  },
  button: {
    backgroundColor: '#38bdf8',
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
