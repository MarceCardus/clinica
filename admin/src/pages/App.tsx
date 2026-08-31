import { useEffect, useMemo, useState } from 'react';

import api from '../hooks/useApi';
import { useAuthStore } from '../hooks/useAuthStore';
import { AuditLog, Market, Match, Odd, TopUp, Tournament, Withdrawal } from '../types';

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

const menuItems = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'topups', label: 'Recargas' },
  { key: 'withdrawals', label: 'Retiros' },
  { key: 'tournaments', label: 'Torneos' },
  { key: 'markets', label: 'Mercados y Cuotas' },
  { key: 'audit', label: 'Auditoría' },
  { key: 'legal', label: 'Avisos legales' }
];

function LoginView() {
  const setAuth = useAuthStore((s) => s.setAuth);
  const [email, setEmail] = useState('admin@example.com');
  const [password, setPassword] = useState('Admin1234!');
  const [error, setError] = useState('');
  const handleSubmit = async (evt: React.FormEvent) => {
    evt.preventDefault();
    try {
      const response = await api.post<LoginResponse>('/auth/login', { email, password });
      setAuth(response.data.access_token, 'admin');
    } catch (err) {
      setError('Credenciales inválidas');
    }
  };

  return (
    <div className="login-container">
      <h1>Backoffice Apuestas</h1>
      <form onSubmit={handleSubmit} className="card">
        <label>Correo</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        <label>Contraseña</label>
        <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
        <button type="submit">Ingresar</button>
        {error && <span className="error">{error}</span>}
      </form>
      <p className="hint">Solo usuarios administradores autorizados.</p>
    </div>
  );
}

function Dashboard() {
  const [topups, setTopups] = useState<TopUp[]>([]);
  const [withdrawals, setWithdrawals] = useState<Withdrawal[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      const tournaments = await api.get<Tournament[]>('/tournaments');
      if (tournaments.data.length > 0) {
        const first = tournaments.data[0];
        const matchesResp = await api.get<Match[]>(`/tournaments/${first.id}/matches`);
        setMatches(matchesResp.data);
      }
      const topupsResp = await api.get<TopUp[]>('/wallet/topups/me');
      setTopups(topupsResp.data);
      const withdrawalsResp = await api.get<Withdrawal[]>('/wallet/withdrawals/me');
      setWithdrawals(withdrawalsResp.data);
    };
    fetchData();
  }, []);

  return (
    <div className="grid">
      <div className="card">
        <h3>Recargas del usuario actual</h3>
        <p>{topups.length} operaciones</p>
      </div>
      <div className="card">
        <h3>Retiros solicitados por el usuario</h3>
        <p>{withdrawals.length} operaciones</p>
      </div>
      <div className="card wide">
        <h3>Próximos partidos</h3>
        <ul>
          {matches.map((m) => (
            <li key={m.id}>
              Partido #{m.id} — {new Date(m.scheduled_at).toLocaleString()} — Estado: {m.state}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function TopupsAdmin() {
  const [items, setItems] = useState<TopUp[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    const response = await api.get<TopUp[]>('/wallet/topups', { params: { status: 'PENDING' } });
    setItems(response.data);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const review = async (id: number, status: 'APPROVED' | 'REJECTED') => {
    await api.patch(`/wallet/topups/${id}`, { status });
    await load();
  };

  return (
    <div>
      <h2>Recargas</h2>
      <p className="hint">Revisar comprobantes y aprobar manualmente.</p>
      {loading && <p>Cargando...</p>}
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Monto</th>
            <th>Banco</th>
            <th>Referencia</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{item.id}</td>
              <td>${item.amount}</td>
              <td>{item.bank_name}</td>
              <td>{item.ref_number}</td>
              <td>{item.status}</td>
              <td>
                {item.status === 'PENDING' ? (
                  <div className="actions">
                    <button onClick={() => review(item.id, 'APPROVED')}>Aprobar</button>
                    <button className="danger" onClick={() => review(item.id, 'REJECTED')}>
                      Rechazar
                    </button>
                  </div>
                ) : (
                  'Revisado'
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WithdrawalsAdmin() {
  const [items, setItems] = useState<Withdrawal[]>([]);

  const load = async () => {
    const response = await api.get<Withdrawal[]>('/wallet/withdrawals', { params: { status: 'REQUESTED' } });
    setItems(response.data);
  };

  useEffect(() => {
    load();
  }, []);

  const review = async (id: number, status: 'PAID' | 'REJECTED') => {
    await api.patch(`/wallet/withdrawals/${id}`, { status });
    await load();
  };

  return (
    <div>
      <h2>Retiros</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Monto</th>
            <th>Alias</th>
            <th>Titular</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{item.id}</td>
              <td>${item.amount}</td>
              <td>{item.bank_alias}</td>
              <td>{item.bank_holder}</td>
              <td>{item.status}</td>
              <td>
                {item.status === 'REQUESTED' && (
                  <div className="actions">
                    <button onClick={() => review(item.id, 'PAID')}>Marcar pagado</button>
                    <button className="danger" onClick={() => review(item.id, 'REJECTED')}>
                      Rechazar
                    </button>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TournamentsAdmin() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [name, setName] = useState('Torneo Corporativo');
  const [company, setCompany] = useState('Empresa');
  const [start, setStart] = useState(() => new Date().toISOString().slice(0, 16));
  const [end, setEnd] = useState(() => new Date(Date.now() + 86400000).toISOString().slice(0, 16));

  const load = async () => {
    const response = await api.get<Tournament[]>('/tournaments');
    setTournaments(response.data);
  };

  useEffect(() => {
    load();
  }, []);

  const createTournament = async (evt: React.FormEvent) => {
    evt.preventDefault();
    await api.post('/tournaments', {
      name,
      company_name: company,
      starts_at: new Date(start).toISOString(),
      ends_at: new Date(end).toISOString(),
      status: 'ACTIVE'
    });
    await load();
  };

  return (
    <div className="grid">
      <div className="card wide">
        <h2>Torneos activos</h2>
        <ul>
          {tournaments.map((t) => (
            <li key={t.id}>
              {t.name} – {t.company_name} – {new Date(t.starts_at).toLocaleDateString()}
            </li>
          ))}
        </ul>
      </div>
      <form className="card" onSubmit={createTournament}>
        <h3>Nuevo torneo</h3>
        <label>Nombre</label>
        <input value={name} onChange={(e) => setName(e.target.value)} required />
        <label>Empresa</label>
        <input value={company} onChange={(e) => setCompany(e.target.value)} required />
        <label>Inicio</label>
        <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} required />
        <label>Fin</label>
        <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} required />
        <button type="submit">Crear torneo</button>
      </form>
    </div>
  );
}

function MarketsAdmin() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selectedTournament, setSelectedTournament] = useState<number | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [markets, setMarkets] = useState<Market[]>([]);
  const [odds, setOdds] = useState<Odd[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<number | null>(null);

  useEffect(() => {
    api.get<Tournament[]>('/tournaments').then((resp) => {
      setTournaments(resp.data);
      if (resp.data.length > 0) {
        setSelectedTournament(resp.data[0].id);
      }
    });
  }, []);

  useEffect(() => {
    if (selectedTournament) {
      api.get<Match[]>(`/tournaments/${selectedTournament}/matches`).then((resp) => {
        setMatches(resp.data);
        if (resp.data.length > 0) {
          setSelectedMatch(resp.data[0].id);
          loadMarkets(resp.data[0].id);
        }
      });
    }
  }, [selectedTournament]);

  const loadMarkets = async (matchId: number) => {
    setSelectedMatch(matchId);
    const response = await api.get<Market[]>(`/tournaments/matches/${matchId}/markets`);
    setMarkets(response.data);
    if (response.data.length > 0) {
      const oddsResp = await api.get<Odd[]>(`/tournaments/markets/${response.data[0].id}/odds`);
      setOdds(oddsResp.data);
    } else {
      setOdds([]);
    }
  };

  const updateMarket = async (marketId: number, status: string) => {
    await api.patch(`/tournaments/markets/${marketId}`, { status });
    if (selectedMatch) {
      await loadMarkets(selectedMatch);
    }
  };

  return (
    <div>
      <h2>Mercados</h2>
      <div className="controls">
        <label>Torneo</label>
        <select value={selectedTournament ?? ''} onChange={(e) => setSelectedTournament(Number(e.target.value))}>
          {tournaments.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </div>
      <div className="grid">
        <div className="card">
          <h3>Partidos</h3>
          <ul>
            {matches.map((match) => (
              <li key={match.id}>
                <button
                  className={`link ${selectedMatch === match.id ? 'active' : ''}`}
                  onClick={() => loadMarkets(match.id)}
                >
                  #{match.id} – {new Date(match.scheduled_at).toLocaleString()} – {match.state}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h3>Mercados</h3>
          <ul>
            {markets.map((market) => (
              <li key={market.id}>
                {market.type} — {market.status}
                <div className="actions">
                  <button onClick={() => updateMarket(market.id, 'LOCKED')}>Lock</button>
                  <button onClick={() => updateMarket(market.id, 'OPEN')}>Abrir</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h3>Cuotas</h3>
          <ul>
            {odds.map((odd) => (
              <li key={odd.id}>
                {odd.selection}: {odd.price}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

function AuditAdmin() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  useEffect(() => {
    api.get<AuditLog[]>('/admin/audit').then((resp) => setLogs(resp.data));
  }, []);
  return (
    <div>
      <h2>Auditoría reciente</h2>
      <table>
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Usuario</th>
            <th>Acción</th>
            <th>Detalle</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id}>
              <td>{new Date(log.created_at).toLocaleString()}</td>
              <td>{log.user_id ?? '—'}</td>
              <td>{log.action}</td>
              <td>{log.summary}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LegalNotice() {
  return (
    <div className="card">
      <h2>Políticas y cumplimiento</h2>
      <p>Solo mayores de 18 años pueden operar en la plataforma.</p>
      <p>
        El saldo virtual refleja transferencias bancarias verificadas. Todos los retiros se pagan vía
        transferencia bancaria al titular validado.
      </p>
      <p>
        Las apuestas se cierran automáticamente 10 minutos antes del inicio del partido. Mantener trazabilidad y
        revisar la bitácora de auditoría con frecuencia.
      </p>
    </div>
  );
}

export default function App() {
  const token = useAuthStore((s) => s.token);
  const logout = useAuthStore((s) => s.logout);
  const [tab, setTab] = useState('dashboard');

  const content = useMemo(() => {
    switch (tab) {
      case 'topups':
        return <TopupsAdmin />;
      case 'withdrawals':
        return <WithdrawalsAdmin />;
      case 'tournaments':
        return <TournamentsAdmin />;
      case 'markets':
        return <MarketsAdmin />;
      case 'audit':
        return <AuditAdmin />;
      case 'legal':
        return <LegalNotice />;
      default:
        return <Dashboard />;
    }
  }, [tab]);

  if (!token) {
    return <LoginView />;
  }

  return (
    <div className="layout">
      <aside>
        <h1>Backoffice</h1>
        <nav>
          {menuItems.map((item) => (
            <button
              key={item.key}
              className={item.key === tab ? 'active' : ''}
              onClick={() => setTab(item.key)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <button className="logout" onClick={logout}>
          Cerrar sesión
        </button>
      </aside>
      <main>{content}</main>
    </div>
  );
}
