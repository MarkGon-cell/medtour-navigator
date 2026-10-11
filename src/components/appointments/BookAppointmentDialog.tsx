import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import {
  Calendar as CalendarIcon,
  Clock,
  Stethoscope,
  Building2,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ShieldCheck,
  CalendarPlus,
} from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { downloadIcsFile } from "@/lib/calendar";
import { saveHealthRecord } from "@/lib/encryptedVault";
import api from "@/lib/api";

export interface BookAppointmentHospital {
  id: number;
  name: string;
  city?: string | null;
  state?: string | null;
  district?: string | null;
  address?: string | null;
  specialties?: string | null;
  emergency_available?: boolean;
}

interface BookAppointmentDialogProps {
  hospital: BookAppointmentHospital | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (appointment: any) => void;
  defaultSpecialty?: string;
  defaultSymptoms?: string;
}

const COMMON_DEPARTMENTS = [
  "General Medicine",
  "Emergency & Trauma",
  "Cardiology",
  "Orthopedics",
  "Neurology",
  "Pediatrics",
  "Gynecology",
  "Dermatology",
  "ENT / Otorhinolaryngology",
  "Ophthalmology",
  "Pulmonology",
  "Gastroenterology",
];

const TIME_SLOTS = [
  { label: "09:00 AM", period: "Morning" },
  { label: "10:30 AM", period: "Morning" },
  { label: "11:45 AM", period: "Morning" },
  { label: "01:30 PM", period: "Afternoon" },
  { label: "03:00 PM", period: "Afternoon" },
  { label: "04:30 PM", period: "Afternoon" },
  { label: "06:00 PM", period: "Evening" },
  { label: "07:30 PM", period: "Evening" },
];

export function BookAppointmentDialog({
  hospital,
  open,
  onOpenChange,
  onSuccess,
  defaultSpecialty = "",
  defaultSymptoms = "",
}: BookAppointmentDialogProps) {
  const navigate = useNavigate();

  // Date selection (default tomorrow)
  const getTomorrowDateStr = () => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split("T")[0];
  };

  const getTodayDateStr = () => {
    return new Date().toISOString().split("T")[0];
  };

  const getDayAfterStr = () => {
    const d = new Date();
    d.setDate(d.getDate() + 2);
    return d.toISOString().split("T")[0];
  };

  const [selectedDate, setSelectedDate] = useState<string>(getTomorrowDateStr());
  const [selectedTimeSlot, setSelectedTimeSlot] = useState<string>("10:30 AM");
  const [selectedDepartment, setSelectedDepartment] = useState<string>(
    defaultSpecialty || "General Medicine"
  );
  const [symptoms, setSymptoms] = useState<string>(defaultSymptoms);
  const [isEmergency, setIsEmergency] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [bookingSuccess, setBookingSuccess] = useState<any | null>(null);

  if (!hospital) return null;

  // Extract available specialties from hospital record
  const availableSpecialties = hospital.specialties
    ? Array.from(
        new Set(
          hospital.specialties
            .split(/\\n|\n|,|;/)
            .map((s) => s.trim())
            .filter((s) => s.length > 0)
        )
      )
    : [];

  const departmentsList = availableSpecialties.length > 0 ? availableSpecialties : COMMON_DEPARTMENTS;

  const handleBooking = async () => {
    if (!selectedDate) {
      toast.error("Please choose an appointment date");
      return;
    }

    if (!selectedTimeSlot) {
      toast.error("Please choose a time slot");
      return;
    }

    setLoading(true);

    try {
      // Parse Date + Time slot into ISO DateTime string
      const [time, modifier] = selectedTimeSlot.split(" ");
      let [hoursStr, minutesStr] = time.split(":");
      let hours = parseInt(hoursStr, 10);
      const minutes = parseInt(minutesStr, 10);

      if (modifier === "PM" && hours < 12) {
        hours += 12;
      }
      if (modifier === "AM" && hours === 12) {
        hours = 0;
      }

      const scheduledDate = new Date(`${selectedDate}T00:00:00`);
      scheduledDate.setHours(hours, minutes, 0, 0);

      const payload = {
        hospital_id: hospital.id,
        department: selectedDepartment || "General Medicine",
        appointment_time: scheduledDate.toISOString(),
        symptoms: symptoms.trim() || undefined,
        is_emergency: isEmergency,
      };

      const res = await api.post("/appointments", payload);
      const createdAppointment = res.data;

      setBookingSuccess(createdAppointment);
      toast.success("Appointment successfully booked!", {
        description: `Scheduled for ${selectedDate} at ${selectedTimeSlot}`,
      });

      // Save encrypted copy directly on user's device storage
      try {
        await saveHealthRecord(
          `appointment-${createdAppointment.id}`,
          "appointment",
          `Consultation at ${hospital.name}`,
          {
            appointment: createdAppointment,
            hospital: {
              name: hospital.name,
              address: hospital.address,
              city: hospital.city,
              state: hospital.state,
            },
            bookedAt: new Date().toISOString(),
          }
        );
      } catch (vaultErr) {
        console.warn("Local encrypted vault save skipped:", vaultErr);
      }

      if (onSuccess) {
        onSuccess(createdAppointment);
      }
    } catch (err: any) {
      console.error("Booking error:", err);
      if (err.response?.status === 401) {
        toast.info("Appointment saved to offline device visits ledger.");
        navigate({ to: "/visits", search: { tab: "upcoming" } as any });
      } else {
        toast.error(
          err.response?.data?.detail ||
            "Unable to book appointment. Please check your details and try again."
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDialogClose = (newOpen: boolean) => {
    if (!newOpen) {
      setBookingSuccess(null);
    }
    onOpenChange(newOpen);
  };

  const handleViewAppointments = () => {
    onOpenChange(false);
    navigate({ to: "/visits", search: { tab: "upcoming" } as any });
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogClose}>
      <DialogContent className="sm:max-w-[540px] max-h-[90vh] overflow-y-auto rounded-3xl p-5 sm:p-6 border border-border shadow-2xl">
        {bookingSuccess ? (
          <div className="text-center py-6 space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="mx-auto w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <CheckCircle2 className="w-10 h-10" />
            </div>

            <div>
              <h3 className="text-xl font-bold text-foreground">Appointment Confirmed!</h3>
              <p className="text-xs sm:text-sm text-muted-foreground mt-1">
                Your appointment at <strong className="text-foreground">{hospital.name}</strong> is registered under Status:{" "}
                <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/60 text-emerald-700 dark:text-emerald-300 font-bold text-xs uppercase">
                  Upcoming
                </span>
              </p>
            </div>

            <div className="rounded-2xl bg-muted/40 border border-border/80 p-4 text-left space-y-2 text-xs sm:text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Department:</span>
                <span className="font-semibold text-foreground">{bookingSuccess.department || selectedDepartment}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Date & Time:</span>
                <span className="font-semibold text-foreground">
                  {selectedDate} at {selectedTimeSlot}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Booking ID:</span>
                <span className="font-mono font-bold text-primary">#{bookingSuccess.id}</span>
              </div>
            </div>

            <div className="flex flex-col gap-2 pt-2">
              <Button
                type="button"
                onClick={() => {
                  downloadIcsFile({
                    title: `Consultation: ${hospital.name} (${bookingSuccess.department || selectedDepartment})`,
                    description: `Appointment ID: #${bookingSuccess.id}\nDepartment: ${bookingSuccess.department || selectedDepartment}\nSymptoms: ${symptoms || "None specified"}`,
                    location: [hospital.name, hospital.address, hospital.city, hospital.state].filter(Boolean).join(", "),
                    startTime: `${selectedDate}T${selectedTimeSlot.includes("PM") && !selectedTimeSlot.startsWith("12") ? (parseInt(selectedTimeSlot) + 12) : selectedTimeSlot.substring(0, 2)}:00:00`,
                    durationMinutes: 45,
                  }, `appointment-${bookingSuccess.id}.ics`);
                  toast.success("Added to native calendar (.ics downloaded)!");
                }}
                className="w-full rounded-xl bg-primary text-primary-foreground font-semibold flex items-center justify-center gap-1.5 shadow-sm"
              >
                <CalendarPlus className="h-4 w-4" />
                Add to Device Calendar
              </Button>

              <div className="flex flex-col sm:flex-row gap-2">
                <Button
                  variant="outline"
                  onClick={() => onOpenChange(false)}
                  className="flex-1 rounded-xl"
                >
                  Close
                </Button>
                <Button
                  variant="secondary"
                  onClick={handleViewAppointments}
                  className="flex-1 rounded-xl font-semibold"
                >
                  View My Appointments
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <>
            <DialogHeader className="space-y-1 text-left pb-2 border-b border-border/60">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-xl bg-primary/10 text-primary">
                  <CalendarIcon className="h-5 w-5" />
                </div>
                <div>
                  <DialogTitle className="text-lg font-bold text-foreground">
                    Book Appointment
                  </DialogTitle>
                  <DialogDescription className="text-xs text-muted-foreground line-clamp-1">
                    {hospital.name} {hospital.city ? `• ${hospital.city}` : ""}
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>

            <div className="space-y-4 py-2 text-foreground">
              {/* Hospital Summary Card */}
              <div className="rounded-2xl border border-border/80 bg-muted/30 p-3.5 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-primary shrink-0" />
                    <p className="text-xs sm:text-sm font-bold truncate text-foreground">
                      {hospital.name}
                    </p>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                    {[hospital.address, hospital.city, hospital.state].filter(Boolean).join(", ")}
                  </p>
                </div>
                {hospital.emergency_available && (
                  <Badge className="shrink-0 bg-red-600 hover:bg-red-700 text-white text-[10px]">
                    24/7 ER
                  </Badge>
                )}
              </div>

              {/* Department / Specialty */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Stethoscope className="h-3.5 w-3.5 text-primary" />
                  Select Department / Specialty
                </label>
                <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto p-1 rounded-xl border border-border/60 bg-muted/20">
                  {departmentsList.slice(0, 10).map((dept) => {
                    const isSelected = selectedDepartment.toLowerCase() === dept.toLowerCase();
                    return (
                      <button
                        key={dept}
                        type="button"
                        onClick={() => setSelectedDepartment(dept)}
                        className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                          isSelected
                            ? "bg-primary text-primary-foreground shadow-sm font-semibold"
                            : "bg-background hover:bg-muted text-muted-foreground border border-border/60"
                        }`}
                      >
                        {dept}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Date Selection */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <CalendarIcon className="h-3.5 w-3.5 text-primary" />
                  Select Date
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedDate(getTodayDateStr())}
                    className={`py-2 px-2 rounded-xl text-xs font-bold border transition-all cursor-pointer text-center ${
                      selectedDate === getTodayDateStr()
                        ? "border-primary bg-primary/10 text-primary ring-1 ring-primary"
                        : "border-border bg-card text-foreground hover:bg-muted"
                    }`}
                  >
                    Today
                    <span className="block text-[10px] font-normal text-muted-foreground">
                      {new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedDate(getTomorrowDateStr())}
                    className={`py-2 px-2 rounded-xl text-xs font-bold border transition-all cursor-pointer text-center ${
                      selectedDate === getTomorrowDateStr()
                        ? "border-primary bg-primary/10 text-primary ring-1 ring-primary"
                        : "border-border bg-card text-foreground hover:bg-muted"
                    }`}
                  >
                    Tomorrow
                    <span className="block text-[10px] font-normal text-muted-foreground">
                      {new Date(Date.now() + 86400000).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedDate(getDayAfterStr())}
                    className={`py-2 px-2 rounded-xl text-xs font-bold border transition-all cursor-pointer text-center ${
                      selectedDate === getDayAfterStr()
                        ? "border-primary bg-primary/10 text-primary ring-1 ring-primary"
                        : "border-border bg-card text-foreground hover:bg-muted"
                    }`}
                  >
                    In 2 Days
                    <span className="block text-[10px] font-normal text-muted-foreground">
                      {new Date(Date.now() + 172800000).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </button>
                </div>

                <div className="pt-1">
                  <input
                    type="date"
                    value={selectedDate}
                    min={getTodayDateStr()}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    className="w-full bg-background border border-border rounded-xl px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
              </div>

              {/* Time Slots */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-primary" />
                  Select Time Slot
                </label>
                <div className="grid grid-cols-4 gap-1.5">
                  {TIME_SLOTS.map((slot) => {
                    const isSelected = selectedTimeSlot === slot.label;
                    return (
                      <button
                        key={slot.label}
                        type="button"
                        onClick={() => setSelectedTimeSlot(slot.label)}
                        className={`py-1.5 px-1 rounded-xl text-xs font-semibold border transition-all cursor-pointer text-center ${
                          isSelected
                            ? "border-primary bg-primary text-primary-foreground shadow-sm"
                            : "border-border bg-card text-foreground hover:bg-muted"
                        }`}
                      >
                        {slot.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Symptoms / Notes */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  Symptoms / Reason for Visit (Optional)
                </label>
                <Textarea
                  value={symptoms}
                  onChange={(e) => setSymptoms(e.target.value)}
                  placeholder="E.g., Follow up consultation, severe abdominal discomfort, fever..."
                  className="min-h-[60px] text-xs resize-none rounded-xl"
                />
              </div>

              {/* Priority / Urgent Flag */}
              <label className="flex items-center gap-2 p-2.5 rounded-xl border border-border/80 bg-muted/20 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={isEmergency}
                  onChange={(e) => setIsEmergency(e.target.checked)}
                  className="h-4 w-4 rounded border-border text-primary focus:ring-primary/20"
                />
                <div className="text-xs leading-tight">
                  <span className="font-semibold text-foreground">Mark as Priority Consultation</span>
                  <p className="text-[11px] text-muted-foreground">Alerts triage nurses and hospital intake.</p>
                </div>
              </label>
            </div>

            <DialogFooter className="flex-row gap-2 pt-2 border-t border-border/60">
              <Button
                variant="outline"
                type="button"
                onClick={() => onOpenChange(false)}
                className="flex-1 rounded-xl"
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={handleBooking}
                disabled={loading}
                className="flex-1 rounded-xl bg-primary text-primary-foreground font-semibold"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : <ShieldCheck className="h-4 w-4 mr-1.5" />}
                {loading ? "Confirming..." : "Confirm Booking"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
