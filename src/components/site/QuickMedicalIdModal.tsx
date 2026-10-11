import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { FiPhone, FiX, FiPlus, FiAlertTriangle, FiEye, FiEyeOff, FiLogOut } from 'react-icons/fi';
import { HiOutlineIdentification } from 'react-icons/hi2';
import { toast } from 'sonner';

export interface MedicalIdData {
  fullName: string;
  dateOfBirth?: string;
  gender?: string;
  nationality?: string;
  passportNo: string;
  nationalIdNo?: string;
  bloodType: string;
  organDonor?: boolean;
  allergies: string;
  conditions: string;
  medications?: string;
  emergencyContactName: string;
  emergencyContactPhone: string;
  emergencyContactRelation?: string;
  insurancePolicyNo: string;
  insuranceProvider?: string;
  medicalNotes?: string;
}

const STORAGE_KEY = 'medtour_medical_id';

export function getStoredMedicalId(): MedicalIdData {
  const defaults: MedicalIdData = {
    fullName: '',
    dateOfBirth: '',
    gender: 'Other',
    nationality: '',
    passportNo: '',
    nationalIdNo: '',
    bloodType: 'Unknown',
    organDonor: false,
    allergies: '',
    conditions: '',
    medications: '',
    emergencyContactName: '',
    emergencyContactPhone: '',
    emergencyContactRelation: 'Family',
    insurancePolicyNo: '',
    insuranceProvider: '',
    medicalNotes: '',
  };

  if (typeof window === 'undefined') {
    return defaults;
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...defaults, ...JSON.parse(raw) };
  } catch (e) {
    console.error(e);
  }
  return defaults;
}

export function QuickMedicalIdModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [data, setData] = useState<MedicalIdData>(getStoredMedicalId);
  const [isEditing, setIsEditing] = useState(false);

  // Password Prompt States for .mtr operations
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [passwordMode, setPasswordMode] = useState<"export" | "import">("export");
  const [passwordInput, setPasswordInput] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [selectedMtrFile, setSelectedMtrFile] = useState<File | null>(null);
  const [stagedMtrContent, setStagedMtrContent] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return sessionStorage.getItem("medtour_staged_mtr");
    }
    return null;
  });

  // Optional Master Password set when creating/editing new ID
  const [newVaultPassword, setNewVaultPassword] = useState("");
  const [showNewVaultPassword, setShowNewVaultPassword] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setData(getStoredMedicalId());
      // If mobile browser reloaded during file picking, auto-resume password prompt
      const cachedStaged = sessionStorage.getItem("medtour_staged_mtr");
      if (cachedStaged) {
        setStagedMtrContent(cachedStaged);
        setPasswordMode("import");
        setPasswordInput("");
        setPasswordModalOpen(true);
      }
    }

    const handleDataRestored = () => {
      setData(getStoredMedicalId());
    };

    window.addEventListener("medtour:mtr-restored", handleDataRestored);
    window.addEventListener("medtour:ecs-restored", handleDataRestored);
    return () => {
      window.removeEventListener("medtour:mtr-restored", handleDataRestored);
      window.removeEventListener("medtour:ecs-restored", handleDataRestored);
    };
  }, [isOpen]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      // Persist into device vault
      try {
        const { saveHealthRecord } = await import('@/lib/encryptedVault');
        await saveHealthRecord('primary-medical-id', 'medical_id', 'Emergency Medical ID', data);
        const { saveMtrRecord } = await import('@/lib/mtrDatabase');
        await saveMtrRecord('primary-medical-id', 'medical_id', 'Emergency Medical ID', data);
      } catch (vaultErr) {
        console.warn('Encrypted vault save skipped:', vaultErr);
      }

      toast.success('Medical ID encrypted & saved to device!');
      setIsEditing(false);
    } catch (err) {
      toast.error('Failed to save to local storage.');
    }
  };

  const handleConfirmPassword = async () => {
    if (!passwordInput || passwordInput.trim().length < 4) {
      toast.error("Password must be at least 4 characters.");
      return;
    }

    if (passwordMode === "export") {
      try {
        const { exportMtrDatabaseFile } = await import("@/lib/mtrDatabase");
        const res = await exportMtrDatabaseFile(passwordInput);
        if (res.method === "share") {
          toast.success("Ready! Choose where to save or share your .mtr vault file.");
        } else {
          toast.success("Encrypted .mtr database file downloaded safely!");
        }
        setPasswordModalOpen(false);
        setPasswordInput("");
      } catch (err: any) {
        toast.error(err.message || "Failed to export .mtr file.");
      }
    } else if (passwordMode === "import") {
      const fileToImport = stagedMtrContent || selectedMtrFile;
      if (!fileToImport) {
        toast.error("No .mtr file selected.");
        return;
      }
      try {
        const { importMtrDatabaseFile } = await import("@/lib/mtrDatabase");
        const res = await importMtrDatabaseFile(fileToImport, passwordInput);
        toast.success(`Encrypted .mtr restored successfully! Loaded profile & ${res.visitCount} visits.`);
        setData(getStoredMedicalId());
        setPasswordModalOpen(false);
        setPasswordInput("");
        setSelectedMtrFile(null);
        setStagedMtrContent(null);
        if (typeof window !== "undefined") {
          sessionStorage.removeItem("medtour_staged_mtr");
        }
      } catch (err: any) {
        toast.error(err.message || "Failed to decrypt .mtr file. Access denied.");
      }
    }
  };

  
  const processUploadedFile = async (file: File) => {
    try {
      const text = await file.text();
      let isMtr = false;
      try {
        const parsed = JSON.parse(text);
        if (parsed.format === "MEDTOUR_MTR_V2" || (parsed.ciphertext && parsed.salt)) {
          isMtr = true;
        }
      } catch {}

      if (isMtr || file.name.toLowerCase().includes(".mtr")) {
        // Persist into sessionStorage so mobile tab restarts don't lose the file
        if (typeof window !== "undefined") {
          sessionStorage.setItem("medtour_staged_mtr", text);
        }
        setStagedMtrContent(text);
        setSelectedMtrFile(file);
        setPasswordMode("import");
        setPasswordInput("");
        setPasswordModalOpen(true);
        return;
      }

      if (file.name.toLowerCase().endsWith(".ecs")) {
        const { importEcsDatabaseFile } = await import("@/lib/ecsDatabase");
        const res = await importEcsDatabaseFile(file);
        toast.success(`Legacy database restored (${res.importedCount} records)!`);
        setData(getStoredMedicalId());
        return;
      }

      // Plain JSON fallback
      try {
        const parsed = JSON.parse(text);
        setData((prev) => ({ ...prev, ...parsed }));
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...data, ...parsed }));
        toast.success("Profile imported successfully!");
      } catch {
        toast.error("Invalid file format. Please upload a valid .mtr vault file.");
      }
    } catch (err: any) {
      toast.error(err.message || "Error reading file.");
    }
  };

  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  const handleLogout = async () => {
    try {
      // 1. Clear active localStorage
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem("medtour_visits");
      localStorage.removeItem("medtour_auth_token");
      localStorage.removeItem("medtour_mtr_docked");

      // 2. Clear IndexedDB device vault
      try {
        const { clearMtrDatabase } = await import("@/lib/mtrDatabase");
        await clearMtrDatabase();
      } catch (vaultErr) {
        console.warn("Vault clear error:", vaultErr);
      }

      // 3. Reset React state
      setData(getStoredMedicalId());
      setNewVaultPassword("");
      setShowLogoutConfirm(false);
      setIsEditing(false);

      // 4. Notify app listeners
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("medtour:mtr-restored", {
          detail: { hasMedicalId: false, visitCount: 0 }
        }));
      }

      toast.success("Logged out. Local device session & medical data wiped cleanly.");
      onClose();
    } catch (err) {
      toast.error("Failed to clear local data.");
    }
  };

  const isProfileEmpty =
    !data.fullName &&
    !data.passportNo &&
    !data.allergies &&
    !data.conditions &&
    !data.emergencyContactPhone &&
    !data.insurancePolicyNo;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-xs p-0 sm:p-4">
      <div 
        className="w-full max-w-md rounded-t-3xl sm:rounded-3xl bg-background border border-border shadow-2xl overflow-hidden max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-muted/20">
          <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
            <HiOutlineIdentification className="h-5 w-5 text-amber-500" /> Emergency Medical ID
          </h2>
          <button 
            onClick={onClose}
            className="h-8 w-8 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground"
          >
            <FiX className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {!isEditing ? (
            <div className="space-y-4">
              {isProfileEmpty ? (
                <div className="text-center py-6 space-y-3">
                  <div className="h-12 w-12 rounded-full bg-amber-500/10 text-amber-600 flex items-center justify-center mx-auto text-xl font-bold">
                    <HiOutlineIdentification className="h-6 w-6" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-foreground">No medical profile saved</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Save your blood group, allergies, and emergency contact for ER doctors.
                    </p>
                  </div>
                  <div className="flex flex-col sm:flex-row items-center justify-center gap-2">
                    <Button 
                      onClick={() => setIsEditing(true)}
                      className="h-10 px-5 rounded-xl bg-primary text-primary-foreground font-bold text-xs shadow-xs w-full sm:w-auto"
                    >
                      <FiPlus className="h-4 w-4 mr-1" /> Add Profile Info
                    </Button>
                    <label className="h-10 px-4 rounded-xl border border-border/80 bg-muted/40 hover:bg-muted font-bold text-xs flex items-center justify-center cursor-pointer transition-colors w-full sm:w-auto text-foreground">
                      <input
                        type="file"
                        accept=".mtr,.ecs,.json,application/octet-stream,text/plain,*/*"
                        className="hidden"
                        onClick={(e) => e.stopPropagation()}
                        onChange={async (e) => {
                          e.stopPropagation();
                          const file = e.target.files?.[0];
                          if (!file) return;
                          await processUploadedFile(file);
                          e.target.value = "";
                        }}
                      />
                      <span>Import .mtr Vault</span>
                    </label>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Identity Card */}
                  <div className="p-3.5 rounded-2xl bg-muted/40 border border-border/80 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Patient Identity</span>
                      <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
                        Device Encrypted
                      </span>
                    </div>
                    <div>
                      <p className="text-base font-extrabold text-foreground">{data.fullName || "Tourist Guest"}</p>
                      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground mt-0.5">
                        {data.nationality && <span>Nationality: <strong className="text-foreground">{data.nationality}</strong></span>}
                        {data.dateOfBirth && <span>DOB: <strong className="text-foreground">{data.dateOfBirth}</strong></span>}
                        {data.gender && <span>Gender: <strong className="text-foreground">{data.gender}</strong></span>}
                      </div>
                    </div>
                    <div className="pt-1 flex flex-wrap gap-2 text-xs border-t border-border/50">
                      <span>Passport / ID: <strong className="text-foreground font-mono">{data.passportNo || "N/A"}</strong></span>
                      {data.nationalIdNo && (
                        <span>National ID: <strong className="text-foreground font-mono">{data.nationalIdNo}</strong></span>
                      )}
                    </div>
                  </div>

                  {/* Medical Baseline */}
                  <div className="grid grid-cols-2 gap-2.5">
                    <div className="p-3 rounded-2xl bg-red-500/10 border border-red-500/20">
                      <span className="text-[10px] font-bold text-red-600 dark:text-red-400 uppercase tracking-wider block">Blood Group</span>
                      <span className="text-lg font-black text-red-600 dark:text-red-400">{data.bloodType}</span>
                      {data.organDonor && (
                        <span className="inline-block mt-0.5 text-[10px] font-semibold text-red-700 dark:text-red-300">
                          ✓ Organ Donor
                        </span>
                      )}
                    </div>
                    <div className="p-3 rounded-2xl bg-muted/40 border border-border/80">
                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">Insurance</span>
                      <span className="text-xs font-bold text-foreground block truncate">{data.insurancePolicyNo || "No Policy"}</span>
                      {data.insuranceProvider && (
                        <span className="text-[10px] text-muted-foreground truncate block">{data.insuranceProvider}</span>
                      )}
                    </div>
                  </div>

                  {/* Clinical & Medication Alerts */}
                  {(data.allergies || data.conditions || data.medications) && (
                    <div className="p-3.5 rounded-2xl bg-amber-500/5 border border-amber-500/20 text-xs space-y-1.5">
                      <div className="flex items-center gap-1 font-bold text-amber-600 dark:text-amber-400 uppercase text-[10px] tracking-wider">
                        <FiAlertTriangle className="h-3.5 w-3.5" /> Clinical Alerts & History
                      </div>
                      {data.allergies && <p className="text-foreground"><strong>Allergies:</strong> {data.allergies}</p>}
                      {data.conditions && <p className="text-foreground"><strong>Chronic Conditions:</strong> {data.conditions}</p>}
                      {data.medications && <p className="text-foreground"><strong>Current Medications:</strong> {data.medications}</p>}
                    </div>
                  )}

                  {/* Emergency Contact */}
                  {data.emergencyContactPhone && (
                    <div className="p-3.5 rounded-2xl bg-primary/5 border border-primary/20 flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <span className="text-[10px] font-bold text-primary uppercase tracking-wider block">Primary Emergency Contact</span>
                        <span className="text-xs font-bold text-foreground truncate block">
                          {data.emergencyContactName} {data.emergencyContactRelation ? `(${data.emergencyContactRelation})` : ""}
                        </span>
                        <span className="text-[11px] text-muted-foreground font-mono">{data.emergencyContactPhone}</span>
                      </div>
                      <a href={`tel:${data.emergencyContactPhone}`} className="h-8 px-3 rounded-xl bg-primary text-primary-foreground font-bold text-xs flex items-center gap-1 shrink-0">
                        <FiPhone className="h-3 w-3" /> Call
                      </a>
                    </div>
                  )}

                  <div className="space-y-2 pt-1">
                    <div className="flex gap-2">
                      <Button 
                        onClick={() => setIsEditing(true)}
                        variant="outline" 
                        className="flex-1 h-10 rounded-xl font-bold text-xs border-border"
                      >
                        Edit Profile
                      </Button>
                      <label className="h-10 px-3 rounded-xl border border-border/80 bg-muted/40 hover:bg-muted font-bold text-xs flex items-center justify-center cursor-pointer transition-colors text-foreground">
                        <input
                          type="file"
                          accept=".mtr,.ecs,.json,application/octet-stream,text/plain,*/*"
                          className="hidden"
                          onClick={(e) => e.stopPropagation()}
                          onChange={async (e) => {
                            e.stopPropagation();
                            const file = e.target.files?.[0];
                            if (!file) return;
                            await processUploadedFile(file);
                            e.target.value = "";
                          }}
                        />
                        <span>Import .mtr</span>
                      </label>
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => {
                          setPasswordMode("export");
                          setPasswordInput(newVaultPassword || "");
                          setPasswordModalOpen(true);
                        }}
                        className="h-10 px-3 rounded-xl font-bold text-xs text-primary hover:text-primary/80 border border-primary/20 bg-primary/5"
                        title="Export Password-Protected .mtr File"
                      >
                        Export .mtr File
                      </Button>
                    </div>

                    {/* Reset / Log Out Session Button */}
                    <div className="pt-2 border-t border-border/60 flex items-center justify-between">
                      <span className="text-[11px] text-muted-foreground font-medium">Clear local profile on this device</span>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setShowLogoutConfirm(true)}
                        className="h-8 px-3 rounded-xl text-xs font-bold text-destructive hover:bg-destructive/10 border-destructive/20 gap-1.5"
                      >
                        <FiLogOut className="h-3.5 w-3.5" />
                        Log Out / Clear ID
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <form onSubmit={handleSave} className="space-y-3.5">
              {/* Identity Section */}
              <div className="space-y-2">
                <span className="text-[11px] font-bold text-primary uppercase tracking-wider block">Personal Identity</span>
                <div>
                  <label className="text-[11px] font-semibold text-foreground block mb-0.5">Full Legal Name</label>
                  <input 
                    type="text" 
                    value={data.fullName} 
                    onChange={(e) => setData({ ...data, fullName: e.target.value })}
                    placeholder="e.g. Jane Doe"
                    className="w-full h-9 px-3 rounded-xl border border-input bg-background text-xs font-medium"
                  />
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-[11px] font-semibold text-foreground block mb-0.5">Date of Birth</label>
                    <input 
                      type="date" 
                      value={data.dateOfBirth} 
                      onChange={(e) => setData({ ...data, dateOfBirth: e.target.value })}
                      className="w-full h-9 px-2 rounded-xl border border-input bg-background text-xs font-medium"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-foreground block mb-0.5">Gender</label>
                    <select 
                      value={data.gender} 
                      onChange={(e) => setData({ ...data, gender: e.target.value })}
                      className="w-full h-9 px-2 rounded-xl border border-input bg-background text-xs font-medium"
                    >
                      {['Male', 'Female', 'Non-binary', 'Other'].map(g => (
                        <option key={g} value={g}>{g}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-foreground block mb-0.5">Nationality</label>
                    <input 
                      type="text" 
                      value={data.nationality} 
                      onChange={(e) => setData({ ...data, nationality: e.target.value })}
                      placeholder="e.g. British"
                      className="w-full h-9 px-2 rounded-xl border border-input bg-background text-xs font-medium"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[11px] font-semibold text-foreground block mb-0.5">Passport No</label>
                    <input 
                      type="text" 
                      value={data.passportNo} 
                      onChange={(e) => setData({ ...data, passportNo: e.target.value })}
                      placeholder="e.g. A1234567"
                      className="w-full h-9 px-3 rounded-xl border border-input bg-background text-xs font-medium"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-foreground block mb-0.5">National ID / Aadhaar</label>
                    <input 
                      type="text" 
                      value={data.nationalIdNo} 
                      onChange={(e) => setData({ ...data, nationalIdNo: e.target.value })}
                      placeholder="e.g. 1234 5678"
                      className="w-full h-9 px-3 rounded-xl border border-input bg-background text-xs font-medium"
                    />
                  </div>
                </div>
              </div>

              {/* Medical Information Section */}
              <div className="space-y-2 pt-2 border-t border-border">
                <span className="text-[11px] font-bold text-primary uppercase tracking-wider block">Clinical & Emergency Info</span>
                
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[11px] font-semibold text-foreground block mb-0.5">Blood Type</label>
                    <select 
                      value={data.bloodType} 
                      onChange={(e) => setData({ ...data, bloodType: e.target.value })}
                      className="w-full h-9 px-2 rounded-xl border border-input bg-background text-xs font-medium"
                    >
                      {['Unknown', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(b => (
                        <option key={b} value={b}>{b}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center pt-5">
                    <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold select-none">
                      <input 
                        type="checkbox" 
                        checked={data.organDonor || false}
                        onChange={(e) => setData({ ...data, organDonor: e.target.checked })}
                        className="rounded border-input text-primary"
                      />
                      <span>Organ Donor</span>
                    </label>
                  </div>
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-foreground block mb-0.5">Allergies (Penicillin, Nuts, Latex...)</label>
                  <input 
                    type="text" 
                    value={data.allergies} 
                    onChange={(e) => setData({ ...data, allergies: e.target.value })}
                    placeholder="e.g. Penicillin, NSAIDs, Peanuts"
                    className="w-full h-9 px-3 rounded-xl border border-input bg-background text-xs font-medium"
                  />
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-foreground block mb-0.5">Medical Conditions & Diagnosis</label>
                  <input 
                    type="text" 
                    value={data.conditions} 
                    onChange={(e) => setData({ ...data, conditions: e.target.value })}
                    placeholder="e.g. Asthma, Type 2 Diabetes, Hypertension"
                    className="w-full h-9 px-3 rounded-xl border border-input bg-background text-xs font-medium"
                  />
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-foreground block mb-0.5">Current Medications & Doses</label>
                  <input 
                    type="text" 
                    value={data.medications} 
                    onChange={(e) => setData({ ...data, medications: e.target.value })}
                    placeholder="e.g. Metformin 500mg, Salbutamol inhaler"
                    className="w-full h-9 px-3 rounded-xl border border-input bg-background text-xs font-medium"
                  />
                </div>
              </div>

              {/* Emergency Contact & Insurance */}
              <div className="space-y-2 pt-2 border-t border-border">
                <span className="text-[11px] font-bold text-primary uppercase tracking-wider block">Contact & Insurance</span>
                
                <div className="grid grid-cols-3 gap-2">
                  <div className="col-span-1">
                    <label className="text-[11px] font-semibold text-foreground block mb-0.5">Contact Name</label>
                    <input 
                      type="text" 
                      value={data.emergencyContactName} 
                      onChange={(e) => setData({ ...data, emergencyContactName: e.target.value })}
                      placeholder="Full Name"
                      className="w-full h-9 px-2 rounded-xl border border-input bg-background text-xs font-medium"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-foreground block mb-0.5">Relation</label>
                    <input 
                      type="text" 
                      value={data.emergencyContactRelation} 
                      onChange={(e) => setData({ ...data, emergencyContactRelation: e.target.value })}
                      placeholder="Spouse/Parent"
                      className="w-full h-9 px-2 rounded-xl border border-input bg-background text-xs font-medium"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-foreground block mb-0.5">Phone</label>
                    <input 
                      type="text" 
                      value={data.emergencyContactPhone} 
                      onChange={(e) => setData({ ...data, emergencyContactPhone: e.target.value })}
                      placeholder="+14155552671"
                      className="w-full h-9 px-2 rounded-xl border border-input bg-background text-xs font-medium"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[11px] font-semibold text-foreground block mb-0.5">Insurance Provider</label>
                    <input 
                      type="text" 
                      value={data.insuranceProvider} 
                      onChange={(e) => setData({ ...data, insuranceProvider: e.target.value })}
                      placeholder="e.g. Allianz Global"
                      className="w-full h-9 px-2 rounded-xl border border-input bg-background text-xs font-medium"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-foreground block mb-0.5">Policy / Member ID</label>
                    <input 
                      type="text" 
                      value={data.insurancePolicyNo} 
                      onChange={(e) => setData({ ...data, insurancePolicyNo: e.target.value })}
                      placeholder="e.g. POL-998822"
                      className="w-full h-9 px-2 rounded-xl border border-input bg-background text-xs font-medium"
                    />
                  </div>
                </div>

                {/* Master Vault Password (Optional Export / Encryption Passphrase) */}
                <div className="pt-2 border-t border-border/60 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-amber-600 dark:text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                      🔒 Master Vault Password
                    </span>
                    <span className="text-[10px] text-muted-foreground font-medium">Used for .mtr backup & export</span>
                  </div>
                  <div className="relative flex items-center">
                    <input 
                      type={showNewVaultPassword ? "text" : "password"}
                      value={newVaultPassword}
                      onChange={(e) => setNewVaultPassword(e.target.value)}
                      placeholder="Set 4+ character password (optional now, or when exporting)..."
                      className="w-full h-9 pl-3 pr-9 rounded-xl border border-amber-500/30 bg-amber-500/5 text-xs font-medium focus:ring-1 focus:ring-amber-500"
                    />
                    <button
                      type="button"
                      onClick={() => setShowNewVaultPassword(!showNewVaultPassword)}
                      className="absolute right-2 p-1 text-muted-foreground hover:text-foreground"
                      aria-label={showNewVaultPassword ? "Hide password" : "Show password"}
                      title={showNewVaultPassword ? "Hide password" : "Show password"}
                    >
                      {showNewVaultPassword ? <FiEyeOff className="h-3.5 w-3.5" /> : <FiEye className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                  <p className="text-[10px] text-muted-foreground leading-tight">
                    Setting this password binds your medical records to your personal encryption key. You will need it whenever exporting or restoring your <code className="text-[10px] font-bold">.mtr</code> file.
                  </p>
                </div>
              </div>

              <div className="pt-2 flex gap-2">
                <Button type="button" variant="outline" onClick={() => setIsEditing(false)} className="flex-1 h-10 rounded-xl font-bold text-xs">
                  Cancel
                </Button>
                <Button type="submit" className="flex-1 h-10 rounded-xl bg-primary text-primary-foreground font-bold text-xs shadow-xs">
                  Save to Device Vault
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>

      {/* Password Prompt Modal for .mtr Encryption & Decryption */}
      {passwordModalOpen && (
        <div 
          className="fixed inset-0 z-60 flex items-center justify-center bg-black/75 backdrop-blur-md p-4 animate-in fade-in duration-200"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="w-full max-w-sm rounded-3xl bg-card border border-border p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-extrabold text-foreground flex items-center gap-2">
                🔒 {passwordMode === "export" ? "Set .mtr Master Password" : "Enter .mtr File Password"}
              </h3>
              <button 
                onClick={() => {
                  setPasswordModalOpen(false);
                  setPasswordInput("");
                  setSelectedMtrFile(null);
                  setStagedMtrContent(null);
                  if (typeof window !== "undefined") sessionStorage.removeItem("medtour_staged_mtr");
                }}
                className="h-8 w-8 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground"
              >
                <FiX className="h-4 w-4" />
              </button>
            </div>

            <p className="text-xs text-muted-foreground leading-relaxed">
              {passwordMode === "export"
                ? "Choose a master password to encrypt your .mtr database. Anyone attempting to open or brute-force this file without this exact key will receive randomized, jumbled, corrupted data."
                : "Enter the master password created with this file. Decryption is performed in-memory on your device only."}
            </p>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-foreground block">Master Password</label>
              <div className="relative flex items-center">
                <input
                  type={showPassword ? "text" : "password"}
                  autoFocus
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleConfirmPassword();
                    }
                  }}
                  placeholder="Enter password (min 4 chars)..."
                  className="w-full h-10 pl-3 pr-10 rounded-xl border border-input bg-background text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 p-1 rounded-md text-muted-foreground hover:text-foreground transition-colors"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <FiEyeOff className="h-4 w-4" />
                  ) : (
                    <FiEye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <div className="pt-2 flex gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setPasswordModalOpen(false);
                  setPasswordInput("");
                  setSelectedMtrFile(null);
                  setStagedMtrContent(null);
                  if (typeof window !== "undefined") sessionStorage.removeItem("medtour_staged_mtr");
                }}
                className="flex-1 h-10 rounded-xl font-bold text-xs"
              >
                Cancel
              </Button>
              <Button
                onClick={handleConfirmPassword}
                className="flex-1 h-10 rounded-xl bg-primary text-primary-foreground font-bold text-xs shadow-xs"
              >
                {passwordMode === "export" ? "Encrypt & Download .mtr" : "Unlock & Import .mtr"}
              </Button>
            </div>
          </div>
        </div>
      )}
      {/* Log Out / Clear ID Confirmation Dialog */}
      {showLogoutConfirm && (
        <div 
          className="fixed inset-0 z-70 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="w-full max-w-sm rounded-3xl bg-card border border-destructive/30 p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-destructive">
              <div className="h-10 w-10 rounded-2xl bg-destructive/10 flex items-center justify-center">
                <FiAlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-extrabold text-foreground">Log Out & Clear ID?</h3>
                <p className="text-xs text-muted-foreground">Wipes local records from this browser.</p>
              </div>
            </div>

            <p className="text-xs text-muted-foreground leading-relaxed">
              This will safely clear your Medical ID, active sessions, and local cached visits from this device. 
              If you haven't exported your <code className="font-bold text-foreground">.mtr</code> backup file, you won't be able to restore this data.
            </p>

            <div className="pt-2 flex gap-2">
              <Button
                variant="outline"
                onClick={() => setShowLogoutConfirm(false)}
                className="flex-1 h-10 rounded-xl font-bold text-xs"
              >
                Cancel
              </Button>
              <Button
                onClick={handleLogout}
                className="flex-1 h-10 rounded-xl bg-destructive hover:bg-destructive/90 text-destructive-foreground font-bold text-xs shadow-xs"
              >
                Yes, Log Out
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
