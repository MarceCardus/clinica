import { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';

import api from '../api';

interface Props {
  onNavigate: (screen: string) => void;
}

interface BalanceResponse {
  balance: string;
}

export default function HomeScreen({ onNavigate }: Props) {
  const [balance, setBalance] = useState('0.00');
  const [matches, setMatches] = useState<any[]>([]);

  useEffect(() => {
    const load = async () => {
      const balanceResp = await api.get<BalanceResponse>('/wallet/balance/me');
      setBalance(balanceResp.data.balance);
      const tournaments = await api.get('/tournaments');
      if (tournaments.data.length > 0) {
        const tournamentId = tournaments.data[0].id;
        const matchesResp = await api.get(`/tournaments/${tournamentId}/matches`);
        setMatches(matchesResp.data.slice(0, 3));
      }
    };
    load();
  }, []);

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Panel principal</Text>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Saldo disponible</Text>
        <Text style={styles.balance}>${balance}</Text>
        <View style={styles.row}>
          <Pressable style={styles.button} onPress={() => onNavigate('TopUp')}>
            <Text style={styles.buttonText}>Recargar</Text>
          </Pressable>
          <Pressable style={styles.buttonOutline} onPress={() => onNavigate('Withdraw')}>
            <Text style={styles.buttonOutlineText}>Retirar</Text>
          </Pressable>
        </View>
      </View>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Próximos partidos</Text>
        {matches.map((match) => (
          <Pressable key={match.id} style={styles.listItem} onPress={() => onNavigate('Bets')}>
            <Text style={styles.listText}>#{match.id} – {new Date(match.scheduled_at).toLocaleString()}</Text>
            <Text style={styles.listSub}>Estado: {match.state}</Text>
          </Pressable>
        ))}
        <Pressable onPress={() => onNavigate('Bets')}>
          <Text style={styles.link}>Ver mercados disponibles</Text>
        </Pressable>
      </View>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Perfil y verificación</Text>
        <Text style={styles.paragraph}>
          Completa tu información de KYC y consulta tus movimientos para mantener trazabilidad.
        </Text>
        <Pressable style={styles.button} onPress={() => onNavigate('Profile')}>
          <Text style={styles.buttonText}>Ver perfil</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 24,
    backgroundColor: '#0f172a',
    gap: 16
  },
  title: {
    color: '#f8fafc',
    fontSize: 28,
    fontWeight: '700',
    marginBottom: 12
  },
  card: {
    backgroundColor: '#1f2937',
    borderRadius: 16,
    padding: 20,
    gap: 12
  },
  cardTitle: {
    color: '#cbd5f5',
    fontWeight: '600'
  },
  balance: {
    color: '#fff',
    fontSize: 32,
    fontWeight: '700'
  },
  row: {
    flexDirection: 'row',
    gap: 12
  },
  button: {
    backgroundColor: '#38bdf8',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    flex: 1,
    alignItems: 'center'
  },
  buttonText: {
    color: '#0f172a',
    fontWeight: '700'
  },
  buttonOutline: {
    borderColor: '#38bdf8',
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
    flex: 1,
    alignItems: 'center'
  },
  buttonOutlineText: {
    color: '#38bdf8',
    fontWeight: '700'
  },
  listItem: {
    backgroundColor: '#0f172a',
    borderRadius: 12,
    padding: 16
  },
  listText: {
    color: '#f8fafc',
    fontWeight: '600'
  },
  listSub: {
    color: '#94a3b8',
    marginTop: 4
  },
  link: {
    color: '#38bdf8',
    textAlign: 'right',
    fontWeight: '600'
  },
  paragraph: {
    color: '#e2e8f0'
  }
});
