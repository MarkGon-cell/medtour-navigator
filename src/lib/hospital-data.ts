export type Hospital = {
  id: number;
  name: string;
  city: string;
  state: string;
  address: string;

  latitude: number;
  longitude: number;

  specialties: string | null;
  languages: string | null;

  consultation_fee: number | null;
  waiting_time: number | null;

  emergency_available: boolean;
  icu_available: boolean;

  rating: number | null;
  phone: string | null;
};