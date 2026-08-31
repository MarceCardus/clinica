import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { View } from 'react-native';

import { useAuthStore } from './store/useAuth';
import LoginScreen from './screens/LoginScreen';
import RegisterScreen from './screens/RegisterScreen';
import HomeScreen from './screens/HomeScreen';
import TopUpScreen from './screens/TopUpScreen';
import BalanceScreen from './screens/BalanceScreen';
import BetScreen from './screens/BetScreen';
import WithdrawScreen from './screens/WithdrawScreen';
import ProfileScreen from './screens/ProfileScreen';

export type RootStackParamList = {
  Login: undefined;
  Register: undefined;
  Home: undefined;
  TopUp: undefined;
  Balance: undefined;
  Bets: undefined;
  Withdraw: undefined;
  Profile: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

function AuthNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Login" component={AuthLogin} />
      <Stack.Screen name="Register" component={AuthRegister} />
    </Stack.Navigator>
  );
}

function AuthLogin({ navigation }: any) {
  const token = useAuthStore((s) => s.token);
  useEffect(() => {
    if (token) {
      navigation.replace('Home');
    }
  }, [token]);
  return <LoginScreen onRegister={() => navigation.navigate('Register')} onSuccess={() => navigation.replace('Home')} />;
}

function AuthRegister({ navigation }: any) {
  return <RegisterScreen onLogin={() => navigation.goBack()} />;
}

function AppNavigator() {
  const logout = useAuthStore((s) => s.logout);
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#0f172a' },
        headerTintColor: '#f8fafc'
      }}
    >
      <Stack.Screen name="Home" options={{ title: 'Inicio', headerRight: () => <LogoutButton onPress={logout} /> }}>
        {({ navigation }) => <HomeScreen onNavigate={(screen) => navigation.navigate(screen as any)} />}
      </Stack.Screen>
      <Stack.Screen name="TopUp" options={{ title: 'Recargar saldo' }}>
        {({ navigation }) => <TopUpScreen onSuccess={() => navigation.navigate('Balance')} />}
      </Stack.Screen>
      <Stack.Screen name="Balance" component={BalanceScreen} options={{ title: 'Mi saldo' }} />
      <Stack.Screen name="Bets" component={BetScreen} options={{ title: 'Mercados' }} />
      <Stack.Screen name="Withdraw" options={{ title: 'Retirar' }}>
        {({ navigation }) => <WithdrawScreen onSuccess={() => navigation.navigate('Balance')} />}
      </Stack.Screen>
      <Stack.Screen name="Profile" component={ProfileScreen} options={{ title: 'Perfil' }} />
    </Stack.Navigator>
  );
}

function LogoutButton({ onPress }: { onPress: () => void }) {
  return <View style={{ width: 32 }}><StatusBar style="light" /><View />;</ncat <<'EOF' > mobile/src/App.tsx
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { Pressable, Text } from 'react-native';

import { useAuthStore } from './store/useAuth';
import LoginScreen from './screens/LoginScreen';
import RegisterScreen from './screens/RegisterScreen';
import HomeScreen from './screens/HomeScreen';
import TopUpScreen from './screens/TopUpScreen';
import BalanceScreen from './screens/BalanceScreen';
import BetScreen from './screens/BetScreen';
import WithdrawScreen from './screens/WithdrawScreen';
import ProfileScreen from './screens/ProfileScreen';

export type RootStackParamList = {
  Login: undefined;
  Register: undefined;
  Home: undefined;
  TopUp: undefined;
  Balance: undefined;
  Bets: undefined;
  Withdraw: undefined;
  Profile: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

function AuthLogin({ navigation }: any) {
  const token = useAuthStore((s) => s.token);
  useEffect(() => {
    if (token) {
      navigation.replace('Home');
    }
  }, [token]);
  return <LoginScreen onRegister={() => navigation.navigate('Register')} onSuccess={() => navigation.replace('Home')} />;
}

function AuthRegister({ navigation }: any) {
  return <RegisterScreen onLogin={() => navigation.goBack()} />;
}

function LogoutButton({ onPress }: { onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={{ padding: 8 }}>
      <Text style={{ color: '#f8fafc', fontWeight: '600' }}>Salir</Text>
    </Pressable>
  );
}

function AppNavigator() {
  const logout = useAuthStore((s) => s.logout);
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#0f172a' },
        headerTintColor: '#f8fafc'
      }}
    >
      <Stack.Screen name="Home" options={{ title: 'Inicio', headerRight: () => <LogoutButton onPress={logout} /> }}>
        {({ navigation }) => <HomeScreen onNavigate={(screen) => navigation.navigate(screen as any)} />}
      </Stack.Screen>
      <Stack.Screen name="TopUp" options={{ title: 'Recargar saldo' }}>
        {({ navigation }) => <TopUpScreen onSuccess={() => navigation.navigate('Balance')} />}
      </Stack.Screen>
      <Stack.Screen name="Balance" component={BalanceScreen} options={{ title: 'Mi saldo' }} />
      <Stack.Screen name="Bets" component={BetScreen} options={{ title: 'Mercados' }} />
      <Stack.Screen name="Withdraw" options={{ title: 'Retirar' }}>
        {({ navigation }) => <WithdrawScreen onSuccess={() => navigation.navigate('Balance')} />}
      </Stack.Screen>
      <Stack.Screen name="Profile" component={ProfileScreen} options={{ title: 'Perfil' }} />
    </Stack.Navigator>
  );
}

export default function App() {
  const token = useAuthStore((s) => s.token);

  return (
    <NavigationContainer>
      <StatusBar style="light" />
      {token ? (
        <AppNavigator />
      ) : (
        <Stack.Navigator screenOptions={{ headerShown: false }}>
          <Stack.Screen name="Login" component={AuthLogin} />
          <Stack.Screen name="Register" component={AuthRegister} />
          <Stack.Screen name="Home" component={AppNavigator} />
        </Stack.Navigator>
      )}
    </NavigationContainer>
  );
}
