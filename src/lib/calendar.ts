/**
 * Device Calendar & Native Interop Helper
 * Allows adding appointments and medical reminders to the user's native phone/device calendar
 * without sign-ups, OAuth, or external permissions.
 */

interface CalendarEventParams {
  title: string;
  description?: string;
  location?: string;
  startTime: string | Date; // ISO string or Date
  durationMinutes?: number;
}

/**
 * Generates an iCalendar (.ics) string.
 * This standard format is recognized natively by iOS, Android, macOS, and Windows.
 */
export function generateIcsContent(event: CalendarEventParams): string {
  const start = new Date(event.startTime);
  const duration = event.durationMinutes || 45;
  const end = new Date(start.getTime() + duration * 60 * 1000);

  const formatDate = (date: Date): string => {
    return date.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
  };

  const cleanText = (str?: string) =>
    (str || "").replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");

  const icsLines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//MedTour Navigator//Medical Appointments//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:medtour-${Date.now()}-${Math.random().toString(36).substring(2, 9)}@medtour.health`,
    `DTSTAMP:${formatDate(new Date())}`,
    `DTSTART:${formatDate(start)}`,
    `DTEND:${formatDate(end)}`,
    `SUMMARY:${cleanText(event.title)}`,
    `DESCRIPTION:${cleanText(event.description || "Healthcare appointment scheduled via MedTour Navigator.")}`,
    `LOCATION:${cleanText(event.location || "")}`,
    "STATUS:CONFIRMED",
    // 24-hour reminder alarm
    "BEGIN:VALARM",
    "TRIGGER:-PT24H",
    "ACTION:DISPLAY",
    "DESCRIPTION:Reminder: Upcoming Hospital Appointment Tomorrow",
    "END:VALARM",
    // 2-hour reminder alarm
    "BEGIN:VALARM",
    "TRIGGER:-PT2H",
    "ACTION:DISPLAY",
    "DESCRIPTION:Reminder: Hospital Appointment in 2 Hours",
    "END:VALARM",
    "END:VEVENT",
    "END:VCALENDAR",
  ];

  return icsLines.join("\r\n");
}

/**
 * Triggers native calendar download / intent.
 * On smartphones (iPhone, Android) tapping this downloads and opens the native calendar app
 * prompting the user to "Add to Calendar".
 */
export function downloadIcsFile(event: CalendarEventParams, filename = "appointment.ics"): void {
  const icsData = generateIcsContent(event);
  const blob = new Blob([icsData], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Generates direct Google Calendar web intent link
 * (Works across mobile Chrome and desktop without file downloads).
 */
export function getGoogleCalendarUrl(event: CalendarEventParams): string {
  const start = new Date(event.startTime);
  const duration = event.durationMinutes || 45;
  const end = new Date(start.getTime() + duration * 60 * 1000);

  const formatGCalDate = (date: Date) =>
    date.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";

  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: event.title,
    dates: `${formatGCalDate(start)}/${formatGCalDate(end)}`,
    details: event.description || "",
    location: event.location || "",
  });

  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}
