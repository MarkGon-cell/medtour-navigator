export type Hospital = {
  id: string;
  name: string;
  specialty: string;
  city: string;
  distanceKm: number;
  rating: number;
  emergency: boolean;
  verified: boolean;
  image?: string;
};

export const mockHospitals: Hospital[] = [
  { id: "h1", name: "Apollo Hospitals", specialty: "Multi-Specialty", city: "New Delhi", distanceKm: 2.4, rating: 4.8, emergency: true, verified: true },
  { id: "h2", name: "Fortis Escorts Heart Institute", specialty: "Cardiology", city: "New Delhi", distanceKm: 4.1, rating: 4.7, emergency: true, verified: true },
  { id: "h3", name: "Max Super Speciality", specialty: "Neurology", city: "Gurugram", distanceKm: 6.8, rating: 4.6, emergency: true, verified: true },
  { id: "h4", name: "AIIMS", specialty: "Government / General", city: "New Delhi", distanceKm: 3.2, rating: 4.9, emergency: true, verified: true },
  { id: "h5", name: "Medanta - The Medicity", specialty: "Oncology", city: "Gurugram", distanceKm: 8.5, rating: 4.7, emergency: false, verified: true },
];

export type Appointment = {
  id: string;
  hospital: string;
  doctor: string;
  specialty: string;
  date: string;
  status: "Confirmed" | "Pending" | "Completed";
};

export const mockAppointments: Appointment[] = [
  { id: "a1", hospital: "Apollo Hospitals", doctor: "Dr. R. Sharma", specialty: "Cardiology", date: "2026-07-15 10:30", status: "Confirmed" },
  { id: "a2", hospital: "AIIMS", doctor: "Dr. P. Nair", specialty: "General Physician", date: "2026-07-18 14:00", status: "Pending" },
  { id: "a3", hospital: "Fortis", doctor: "Dr. S. Kapoor", specialty: "Orthopedics", date: "2026-06-30 09:00", status: "Completed" },
];

export const mockNotifications = [
  { id: "n1", title: "Appointment confirmed", body: "Your visit at Apollo is confirmed for Jul 15.", time: "2h" },
  { id: "n2", title: "AI Recommendation", body: "3 new hospitals matched your travel plan.", time: "1d" },
  { id: "n3", title: "Emergency contacts updated", body: "Local SOS numbers loaded for New Delhi.", time: "3d" },
];
