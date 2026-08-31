export interface TopUp {
  id: number;
  user_id: number;
  amount: string;
  bank_name: string;
  ref_number: string;
  proof_url: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  created_at: string;
}

export interface Withdrawal {
  id: number;
  user_id: number;
  amount: string;
  bank_alias: string;
  bank_holder: string;
  status: 'REQUESTED' | 'PAID' | 'REJECTED';
  created_at: string;
}

export interface Tournament {
  id: number;
  name: string;
  company_name: string;
  starts_at: string;
  ends_at: string;
  status: string;
}

export interface Match {
  id: number;
  tournament_id: number;
  home_team_id: number;
  away_team_id: number;
  scheduled_at: string;
  state: string;
  home_score: number;
  away_score: number;
  locked_bool: boolean;
}

export interface Market {
  id: number;
  match_id: number;
  type: string;
  line?: number;
  status: string;
}

export interface Odd {
  id: number;
  market_id: number;
  selection: string;
  price: number;
}

export interface AuditLog {
  id: number;
  user_id?: number;
  action: string;
  entity: string;
  summary: string;
  created_at: string;
}
