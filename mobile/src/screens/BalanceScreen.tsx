import { useEffect, useState } from 'react';
import { View, Text, StyleSheet, FlatList } from 'react-native';

import api from '../api';

interface LedgerEntry {
  id: number;
  type: string;
  amount: string;
  balance_after: string;
  created_at: string;
}

interface BalanceResponse {
  balance: string;
}

export default function BalanceScreen() {
  const [balance, setBalance] = useState('0.00');
  const [entries, setEntries] = useState<LedgerEntry[]>([]);

  useEffect(() => {
    const load = async () => {
      const balanceResp = await api.get<BalanceResponse>('/wallet/balance/me');
      setBalance(balanceResp.data.balance);
      const ledgerResp = await api.get<LedgerEntry[]>('/wallet/ledger/me');
      setEntries(ledgerResp.data);
    };
    load();
  }, []);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Saldo actual</Text>
      <Text style={styles.balance}>${balance}</Text>
      <Text style={styles.subtitle}>Historial</Text>
      <FlatList
        data={entries}
        keyExtractor={(item) => item.id.toString()}
        renderItem={({ item }) => (
          <View style={styles.item}>
            <Text style={styles.itemTitle}>{item.type}</Text>
            <Text style={styles.itemAmount}>{item.amount}</Text>
            <Text style={styles.itemDate}>{new Date(item.created_at).toLocaleString()}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
    padding: 24
  },
  title: {
    color: '#fff',
    fontSize: 26,
    fontWeight: '700'
  },
  balance: {
    color: '#38bdf8',
    fontSize: 32,
    fontWeight: '700',
    marginVertical: 12
  },
  subtitle: {
    color: '#cbd5f5',
    fontWeight: '600',
    marginBottom: 12
  },
  item: {
    backgroundColor: '#1f2937',
    borderRadius: 12,
    padding: 16,
    marginBottom: 8
  },
  itemTitle: {
    color: '#f8fafc',
    fontWeight: '600'
  },
  itemAmount: {
    color: '#22d3ee',
    marginTop: 4
  },
  itemDate: {
    color: '#94a3b8',
    marginTop: 4
  }
});
