import { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Pressable, TextInput, ScrollView } from 'react-native';

import api from '../api';

interface Tournament {
  id: number;
  name: string;
}

interface Match {
  id: number;
  scheduled_at: string;
  state: string;
}

interface Market {
  id: number;
  type: string;
  status: string;
}

interface Odd {
  id: number;
  selection: string;
  price: number;
}

export default function BetScreen() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [markets, setMarkets] = useState<Market[]>([]);
  const [odds, setOdds] = useState<Odd[]>([]);
  const [stake, setStake] = useState('50');
  const [message, setMessage] = useState('');

  useEffect(() => {
    api.get<Tournament[]>('/tournaments').then((resp) => {
      setTournaments(resp.data);
      if (resp.data.length) {
        selectTournament(resp.data[0].id);
      }
    });
  }, []);

  const selectTournament = async (id: number) => {
    const matchesResp = await api.get<Match[]>(`/tournaments/${id}/matches`);
    setMatches(matchesResp.data);
    if (matchesResp.data.length) {
      selectMatch(matchesResp.data[0].id);
    }
  };

  const selectMatch = async (id: number) => {
    const marketsResp = await api.get<Market[]>(`/tournaments/matches/${id}/markets`);
    setMarkets(marketsResp.data);
    if (marketsResp.data.length) {
      selectMarket(marketsResp.data[0].id);
    } else {
      setOdds([]);
    }
  };

  const selectMarket = async (id: number) => {
    const oddsResp = await api.get<Odd[]>(`/tournaments/markets/${id}/odds`);
    setOdds(oddsResp.data);
  };

  const placeBet = async (marketId: number, selection: string) => {
    try {
      await api.post('/bets', { market_id: marketId, selection, stake });
      setMessage('Apuesta registrada');
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'No se pudo apostar');
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Mercados disponibles</Text>
      <TextInput style={styles.input} value={stake} onChangeText={setStake} keyboardType="numeric" placeholder="Monto" />
      <Text style={styles.section}>Torneos</Text>
      <View style={styles.row}>
        {tournaments.map((t) => (
          <Pressable key={t.id} style={styles.pill} onPress={() => selectTournament(t.id)}>
            <Text style={styles.pillText}>{t.name}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={styles.section}>Partidos</Text>
      {matches.map((match) => (
        <Pressable key={match.id} style={styles.item} onPress={() => selectMatch(match.id)}>
          <Text style={styles.itemTitle}>#{match.id}</Text>
          <Text style={styles.itemSub}>{new Date(match.scheduled_at).toLocaleString()}</Text>
          <Text style={styles.itemSub}>Estado: {match.state}</Text>
        </Pressable>
      ))}
      <Text style={styles.section}>Mercados</Text>
      {markets.map((market) => (
        <View key={market.id} style={styles.market}>
          <Text style={styles.marketTitle}>{market.type} — {market.status}</Text>
          <View style={styles.row}>
            {odds.map((odd) => (
              <Pressable key={odd.id} style={styles.odd} onPress={() => placeBet(market.id, odd.selection)}>
                <Text style={styles.oddText}>{odd.selection}</Text>
                <Text style={styles.oddPrice}>{odd.price.toFixed(2)}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ))}
      {message && <Text style={styles.message}>{message}</Text>}
    </ScrollView>
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
    fontWeight: '700',
    marginBottom: 12
  },
  section: {
    color: '#cbd5f5',
    marginTop: 16,
    marginBottom: 8,
    fontWeight: '600'
  },
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8
  },
  pill: {
    backgroundColor: '#1f2937',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 16
  },
  pillText: {
    color: '#f8fafc'
  },
  item: {
    backgroundColor: '#1f2937',
    padding: 16,
    borderRadius: 12,
    marginBottom: 8
  },
  itemTitle: {
    color: '#f8fafc',
    fontWeight: '600'
  },
  itemSub: {
    color: '#94a3b8'
  },
  market: {
    backgroundColor: '#1f2937',
    padding: 16,
    borderRadius: 12,
    marginBottom: 12
  },
  marketTitle: {
    color: '#f8fafc',
    fontWeight: '600',
    marginBottom: 8
  },
  odd: {
    backgroundColor: '#0f172a',
    borderRadius: 12,
    padding: 12,
    minWidth: 90,
    alignItems: 'center'
  },
  oddText: {
    color: '#e2e8f0',
    fontWeight: '600'
  },
  oddPrice: {
    color: '#38bdf8',
    marginTop: 4
  },
  input: {
    backgroundColor: '#1f2937',
    color: '#fff',
    borderRadius: 12,
    padding: 12
  },
  message: {
    color: '#cbd5f5',
    marginTop: 12
  }
});
