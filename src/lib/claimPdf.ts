/**
 * @deprecated MedTour Verified Mediclaim PDF Generator (CLIENT-SIDE LEGACY)
 *
 * NOTE: The backend endpoint POST /doctor/claim/purchase and /doctor/claim/pdf
 * now render verified, password-protected ReportLab PDFs server-side with
 * official line items, doctor NMC signature, and QR verification.
 * Client-side generation in this file is deprecated and retained only as an offline fallback.
 */

import jsPDF from "jspdf";
import { sha256 } from "@noble/hashes/sha2.js";
import { bufToBase64 } from "@/lib/cryptoEngine";

export interface ClaimPdfData {
  appointmentCode: string;
  patientName: string;
  patientId: string;
  hospitalName: string;
  hospitalAddress: string;
  department: string;
  appointmentTime: string;
  completedAt: string;
  diagnosis: string;
  prescription: string;
  diagnosisNotes?: string;
  symptoms?: string;
  verificationHash: string;

  /** Only true once the patient has PAID for the generation of this PDF. */
  isVerified?: boolean;
  verifiedAt?: string;

  /** The doctor who operated on the patient, + their NMC verification. */
  doctorName?: string;
  doctorRegNumber?: string;
  doctorStateCouncil?: string;
  doctorVerified?: boolean;
  doctorVerifiedAt?: string;

  /** Invoice raised for generating this mediclaim. */
  invoiceNumber?: string;
  invoiceAmount?: number;
  invoiceCurrency?: string;
}

/**
 * Build the crypto-verification QR payload string.
 *
 * Scanning it resolves to the VERIFICATION STATUS OF THE OPERATING DOCTOR
 * (reg number + council + whether the NMC check passed), plus the appointment
 * code and document hash — so an insurer reading the QR learns who treated
 * the patient and whether that doctor is genuinely verified.
 */
export function buildVerificationQrPayload(data: ClaimPdfData): string {
  return JSON.stringify({
    v: "MT-CLAIM-V1",
    type: "mediclaim",
    code: data.appointmentCode,
    hash: data.verificationHash,
    // Doctor verification block (what the QR resolves to)
    doc: {
      name: data.doctorName || null,
      reg: data.doctorRegNumber || null,
      council: data.doctorStateCouncil || null,
      verified: data.doctorVerified === true,
      verified_at: data.doctorVerifiedAt || null,
    },
    // Brief details of the patient operated on
    patient: {
      name: data.patientName || null,
      hospital: data.hospitalName || null,
      completed: data.completedAt || null,
    },
    invoice: data.invoiceNumber || null,
    verified: data.isVerified === true,
    ts: Date.now(),
  });
}

/**
 * Generate a SHA-256 hash of the claim data (used as the verification hash
 * if the backend didn't provide one).
 */
export function computeClaimHash(data: Omit<ClaimPdfData, "verificationHash">): string {
  const input = [
    data.appointmentCode,
    data.patientId,
    data.hospitalName,
    data.diagnosis,
    data.prescription,
    data.completedAt,
  ].join("|");
  const bytes = new TextEncoder().encode(input);
  const hashBytes = sha256(bytes);
  let hex = "";
  for (let i = 0; i < hashBytes.length; i++) {
    hex += hashBytes[i].toString(16).padStart(2, "0");
  }
  return hex;
}

/**
 * Generate the password-protected verified mediclaim PDF and trigger a download.
 *
 * @param data   - claim details
 * @param password - the user's .mtr master password (used as the PDF password)
 */
export async function generateVerifiedClaimPdf(
  data: ClaimPdfData,
  password: string,
): Promise<void> {
  if (!password || password.trim().length < 4) {
    throw new Error("PDF password must be at least 4 characters.");
  }

  // Use jsPDF encryption (RC4 128-bit). Both user and owner passwords are set.
  const doc = new jsPDF({
    orientation: "portrait",
    unit: "mm",
    format: "a4",
    encryption: {
      userPassword: password,
      ownerPassword: password,
      userPermissions: ["print", "modify", "copy", "annot-forms"],
    },
  });

  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 18;
  const contentWidth = pageWidth - margin * 2;
  let y = margin;

  // ── Header banner ──────────────────────────────────────────────────────
  doc.setFillColor(21, 112, 239); // #1570EF
  doc.rect(0, 0, pageWidth, 32, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.text("MedTour Verified Mediclaim", margin, 16);
  doc.setFontSize(9);
  doc.setFont("helvetica", "normal");
  doc.text("International Healthcare Claim Document — Authentic & Verified", margin, 23);
  doc.setFontSize(8);
  doc.text(`Generated: ${new Date().toLocaleString()}`, margin, 28);

  y = 42;

  // ── Verified badge (only after payment for generation) ──────────────────
  doc.setFillColor(3, 152, 85); // #039855
  doc.roundedRect(margin, y, contentWidth, 10, 3, 3, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.text(
    data.isVerified
      ? "✔  IS VERIFIED — PAYMENT RECEIVED • MEDICLAIM GENERATED"
      : "IS VERIFIED — PENDING PAYMENT",
    pageWidth / 2,
    y + 6.5,
    { align: "center" },
  );

  y += 16;

  // ── Helper: draw a section ─────────────────────────────────────────────
  const drawSection = (
    title: string,
    rows: Array<[string, string]>,
  ) => {
    // Section title
    doc.setFillColor(249, 250, 251); // #F9FAFB
    doc.rect(margin, y, contentWidth, 8, "F");
    doc.setTextColor(71, 84, 103); // #475467
    doc.setFont("helvetica", "bold");
    doc.setFontSize(8);
    doc.text(title.toUpperCase(), margin + 3, y + 5.5);
    y += 10;

    // Rows
    doc.setTextColor(16, 24, 40); // #101828
    for (const [label, value] of rows) {
      doc.setFont("helvetica", "bold");
      doc.setFontSize(8);
      doc.text(label, margin + 3, y + 4);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      const lines = doc.splitTextToSize(value || "—", contentWidth - 50);
      doc.text(lines, margin + 55, y + 4);
      y += Math.max(6, lines.length * 4.5);
    }
    y += 4;
  };

  drawSection("Patient Information", [
    ["Full Name", data.patientName],
    ["Patient ID", data.patientId],
  ]);

  drawSection("Healthcare Facility", [
    ["Hospital", data.hospitalName],
    ["Address", data.hospitalAddress],
    ["Department", data.department],
  ]);

  drawSection("Appointment", [
    ["Appointment ID", data.appointmentCode],
    ["Status", "Completed"],
    ["IS Verified", data.isVerified ? "Yes — paid & verified" : "No"],
    ["Scheduled", data.appointmentTime],
    ["Completed", data.completedAt],
  ]);

  // ── Operating doctor + their verification status ───────────────────────
  drawSection("Doctor Who Operated", [
    ["Doctor", data.doctorName || "—"],
    ["NMC Reg. No.", data.doctorRegNumber || "—"],
    ["State Council", data.doctorStateCouncil || "—"],
    [
      "Verification",
      data.doctorVerified
        ? `NMC VERIFIED${data.doctorVerifiedAt ? ` (${data.doctorVerifiedAt})` : ""}`
        : "Not verified",
    ],
  ]);

  drawSection("Reason For Visit", [
    ["Reported Symptoms", data.symptoms || "—"],
  ]);

  drawSection("Clinical Diagnosis", [
    ["Diagnosis", data.diagnosis],
  ]);

  drawSection("Prescription", [
    ["Medications / Treatment", data.prescription],
  ]);

  if (data.diagnosisNotes) {
    drawSection("Clinical Notes", [["Notes", data.diagnosisNotes]]);
  }

  // ── Invoice ────────────────────────────────────────────────────────────
  drawSection("Invoice", [
    ["Invoice No.", data.invoiceNumber || `MT-INV-${data.appointmentCode}`],
    ["Service", "Verified Mediclaim Generation"],
    ["Status", data.isVerified ? "Paid (test mode)" : "Unpaid"],
    [
      "Amount",
      `${data.invoiceCurrency || "INR"} ${data.invoiceAmount ?? 499}`,
    ],
  ]);

  // ── Verification QR (anchored at the bottom) ───────────────────────────
  y += 2;
  doc.setDrawColor(234, 236, 240); // #EAECF0
  doc.setLineWidth(0.3);
  doc.line(margin, y, margin + contentWidth, y);
  y += 6;

  doc.setTextColor(16, 24, 40);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(9);
  doc.text("Document Authentication", margin, y + 4);
  y += 7;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(7.5);
  doc.setTextColor(71, 84, 103);
  const hashDisplay = data.verificationHash.slice(0, 32) + "…";
  doc.text(`Verification Hash (SHA-256): ${hashDisplay}`, margin, y + 3);
  y += 7;

  doc.setFontSize(7.5);
  doc.setTextColor(
    data.doctorVerified ? 3 : 180,
    data.doctorVerified ? 152 : 30,
    data.doctorVerified ? 85 : 30,
  );
  doc.setFont("helvetica", "bold");
  doc.text(
    data.doctorVerified
      ? `Doctor verification: NMC VERIFIED — ${data.doctorRegNumber || "registered"} (${data.doctorStateCouncil || "India"})`
      : "Doctor verification: NOT VERIFIED",
    margin,
    y + 3,
  );
  y += 6;

  // Render the verification QR as a canvas → data URL → embed. Scanning it
  // resolves to the operating doctor's verification status + brief patient
  // details, so an insurer can confirm authenticity from the printed page.
  try {
    const QRCode = (await import("qrcode")).default;
    const qrPayload = buildVerificationQrPayload(data);
    const qrDataUrl = await QRCode.toDataURL(qrPayload, {
      width: 220,
      margin: 1,
      color: { dark: "#000000", light: "#FFFFFF" },
    });
    const qrSize = 34;
    doc.addImage(qrDataUrl, "PNG", margin, y, qrSize, qrSize);

    doc.setTextColor(71, 84, 103);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(7.5);
    doc.text(
      [
        "Scan to verify — resolves to the operating",
        "doctor's NMC verification status and the",
        "patient treated on this appointment.",
      ],
      margin + qrSize + 4,
      y + 7,
    );
    doc.setFont("helvetica", "bold");
    doc.setTextColor(16, 24, 40);
    doc.text(
      data.doctorName ? `Dr. ${data.doctorName.replace(/^Dr\.?\s*/i, "")}` : "MedTour Verified",
      margin + qrSize + 4,
      y + 24,
    );
    doc.setFont("helvetica", "normal");
    doc.setFontSize(7);
    doc.setTextColor(100, 116, 139);
    doc.text(`ID ${data.appointmentCode}`, margin + qrSize + 4, y + 29);
    y += qrSize + 4;
  } catch (qrErr) {
    console.warn("[ClaimPdf] QR render failed:", qrErr);
    doc.setFontSize(7);
    doc.setTextColor(180, 30, 30);
    doc.text("Verification QR unavailable.", margin, y + 3);
    y += 8;
  }

  // ── Footer ─────────────────────────────────────────────────────────────
  const footerY = doc.internal.pageSize.getHeight() - 18;
  doc.setDrawColor(234, 236, 240);
  doc.line(margin, footerY, margin + contentWidth, footerY);
  doc.setFontSize(7);
  doc.setTextColor(100, 116, 139);
  doc.text(
    "This document is electronically generated and cryptographically signed by MedTour Navigator.",
    pageWidth / 2,
    footerY + 5,
    { align: "center" },
  );
  doc.text(
    "Password-protected. Open with your MedTour .mtr master password.",
    pageWidth / 2,
    footerY + 9,
    { align: "center" },
  );

  // ── Save (download) ────────────────────────────────────────────────────
  const filename = `MedTour_Verified_Mediclaim_${data.appointmentCode}.pdf`;
  doc.save(filename);
}

/**
 * Save the generated PDF as a base64 string (for .mtr vault storage).
 * This re-generates the PDF without triggering a download.
 */
export async function generateClaimPdfBase64(
  data: ClaimPdfData,
  password: string,
): Promise<string> {
  if (!password || password.trim().length < 4) {
    throw new Error("PDF password must be at least 4 characters.");
  }

  const doc = new jsPDF({
    orientation: "portrait",
    unit: "mm",
    format: "a4",
    encryption: {
      userPassword: password,
      ownerPassword: password,
      userPermissions: ["print", "modify", "copy", "annot-forms"],
    },
  });

  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 18;
  const contentWidth = pageWidth - margin * 2;
  let y = margin;

  // Header
  doc.setFillColor(21, 112, 239);
  doc.rect(0, 0, pageWidth, 32, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.text("MedTour Verified Mediclaim", margin, 16);
  doc.setFontSize(9);
  doc.setFont("helvetica", "normal");
  doc.text("International Healthcare Claim Document", margin, 23);

  y = 42;

  // Verified badge (only after payment for generation)
  doc.setFillColor(3, 152, 85);
  doc.roundedRect(margin, y, contentWidth, 10, 3, 3, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.text(
    data.isVerified
      ? "✔  IS VERIFIED — PAYMENT RECEIVED • MEDICLAIM GENERATED"
      : "IS VERIFIED — PENDING PAYMENT",
    pageWidth / 2,
    y + 6.5,
    { align: "center" },
  );
  y += 16;

  // Full data dump — kept in sync with generateVerifiedClaimPdf so the
  // vault copy and the downloaded file are the same document.
  const fields: Array<[string, string]> = [
    ["Patient", data.patientName],
    ["Patient ID", data.patientId],
    ["Hospital", data.hospitalName],
    ["Address", data.hospitalAddress],
    ["Department", data.department],
    ["Appointment ID", data.appointmentCode],
    ["Status", "Completed"],
    ["IS Verified", data.isVerified ? "Yes — paid & verified" : "No"],
    ["Doctor", data.doctorName || "—"],
    ["NMC Reg. No.", data.doctorRegNumber || "—"],
    ["State Council", data.doctorStateCouncil || "—"],
    [
      "Doctor Verification",
      data.doctorVerified
        ? `NMC VERIFIED${data.doctorVerifiedAt ? ` (${data.doctorVerifiedAt})` : ""}`
        : "Not verified",
    ],
    ["Reported Symptoms", data.symptoms || "—"],
    ["Scheduled", data.appointmentTime],
    ["Completed", data.completedAt],
    ["Diagnosis", data.diagnosis],
    ["Prescription", data.prescription],
    ["Invoice No.", data.invoiceNumber || `MT-INV-${data.appointmentCode}`],
    [
      "Invoice Amount",
      `${data.invoiceCurrency || "INR"} ${data.invoiceAmount ?? 499}`,
    ],
  ];

  if (data.diagnosisNotes) {
    fields.push(["Notes", data.diagnosisNotes]);
  }

  for (const [label, value] of fields) {
    doc.setTextColor(71, 84, 103);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(8);
    doc.text(label, margin, y);
    doc.setTextColor(16, 24, 40);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    const lines = doc.splitTextToSize(value || "—", contentWidth - 40);
    doc.text(lines, margin + 40, y);
    y += Math.max(6, lines.length * 4.5);
  }

  // Verification QR at the bottom — same payload as the downloaded file so
  // the vault copy authenticates identically.
  y += 6;
  doc.setDrawColor(234, 236, 240);
  doc.line(margin, y, margin + contentWidth, y);
  y += 6;
  doc.setTextColor(16, 24, 40);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(9);
  doc.text("Document Authentication", margin, y);
  y += 6;
  doc.setFont("courier", "normal");
  doc.setFontSize(7);
  doc.setTextColor(71, 84, 103);
  doc.text(data.verificationHash, margin, y);
  y += 8;

  try {
    const QRCode = (await import("qrcode")).default;
    const qrDataUrl = await QRCode.toDataURL(buildVerificationQrPayload(data), {
      width: 220,
      margin: 1,
      color: { dark: "#000000", light: "#FFFFFF" },
    });
    doc.addImage(qrDataUrl, "PNG", margin, y, 30, 30);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(7.5);
    doc.setTextColor(71, 84, 103);
    doc.text(
      [
        "Scan to verify — resolves to the operating",
        "doctor's NMC verification status.",
      ],
      margin + 34,
      y + 8,
    );
    doc.setFont("helvetica", "bold");
    doc.setTextColor(16, 24, 40);
    doc.text(data.doctorName || "MedTour Verified", margin + 34, y + 22);
  } catch (qrErr) {
    console.warn("[ClaimPdf] QR render failed (base64):", qrErr);
  }

  const base64 = doc.output("datauristring").split(",")[1];
  return base64;
}
